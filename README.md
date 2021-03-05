# project101-tf-eks-jenkins

Summary
* CI/CD project using provisioning EKS cluster through Terraform. 
* Deploy Jenkins to EKS through EFS. 
* Jenkins creating pod agents when CI/CD pipeline start and destroy it when pipeline finish.
* In pipeline we build container from app in repo push it to docker hub and after delpoy to EKS cluster.

## Prepairing proccess. Run and configure aws-cli container, install need tools for wsl and tools for k8s cluster.

### Run Amazon CLI and conigure it.

```
docker run -it --rm -v ${PWD}:/work -w /work --entrypoint /bin/sh amazon/aws-cli:latest
yum install -y jq gzip nano tar git curl wget
```

### Install kubectl, eksctl, terraform.

```
# kubectl
curl -LO https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl
chmod +x ./kubectl && mv ./kubectl /usr/local/bin/kubectl

# eksctl (if need)
curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
mv /tmp/eksctl /usr/local/bin

# terraform install
yum install -y yum-utils
yum-config-manager --add-repo https://rpm.releases.hashicorp.com/AmazonLinux/hashicorp.repo
yum -y install terraform

```

### Configure AWS credentials and provisioning EKS cluster

```
# Configure your credenrtials from before created IAM account with all needed permissions
aws configure

# Init and deploy
terraform init
terraform apply

# update kube config after EKS created.
aws eks update-kubeconfig --name cluster-name --region eu-central-1
cp ~/.kube/config .

```

### Setup our Cloud Storage 

```
# deploy EFS storage driver
kubectl apply -k "github.com/kubernetes-sigs/aws-efs-csi-driver/deploy/kubernetes/overlays/stable/?ref=master"

# get VPC ID
aws eks describe-cluster --name getting-started-eks --query "cluster.resourcesVpcConfig.vpcId" --output text
# Get CIDR range
aws ec2 describe-vpcs --vpc-ids vpc-id --query "Vpcs[].CidrBlock" --output text

# security for our instances to access file storage
aws ec2 create-security-group --description efs-test-sg --group-name efs-sg --vpc-id VPC_ID
aws ec2 authorize-security-group-ingress --group-id sg-xxx  --protocol tcp --port 2049 --cidr VPC_CIDR

# create storage
aws efs create-file-system --creation-token eks-efs

# create mount point 
aws efs create-mount-target --file-system-id FileSystemId --subnet-id SubnetID --security-group GroupID

# grab our volume handle to update our PV YAML
aws efs describe-file-systems --query "FileSystems[*].FileSystemId" --output text

```

### Setup a namespace

```
kubectl create ns jenkins

```

### Setup our storage for Jenkins

```
kubectl get storageclass

# create volume (copy fs-xxxxxx to file)
kubectl apply -f ./jenkins/amazon-eks/jenkins.pv.yaml 
kubectl get pv

# create volume claim
kubectl apply -n jenkins -f ./jenkins/amazon-eks/jenkins.pvc.yaml
kubectl -n jenkins get pvc

```

### Deploy Jenkins

```
# rbac
kubectl apply -n jenkins -f ./jenkins/jenkins.rbac.yaml 
kubectl apply -n jenkins -f ./jenkins/jenkins.deployment.yaml
kubectl -n jenkins get pods

```

### Expose a service for agents

```
kubectl apply -n jenkins -f ./jenkins/jenkins.service.yaml 

```

### Jenkins Initial Setup

```
kubectl -n jenkins exec -it <podname> cat /var/jenkins_home/secrets/initialAdminPassword
kubectl port-forward -n jenkins <podname> 8080

# setup user and recommended basic plugins
# let it continue while we move on!

```

### SSH to our node to get Docker user info

```
eval $(ssh-agent)
ssh-add ~/.ssh/id_rsa
ssh -i ~/.ssh/id_rsa ec2-user@ec2-YourIP.eu-central-1.compute.amazonaws.com
id -u docker
cat /etc/group
# Get user ID for docker
# Get group ID for docker
```
### Docker Jenkins Agent

Docker file is [here](../dockerfiles/dockerfile) <br/>

```
# you can build it

cd ./jenkins/dockerfiles/
docker build . -t aimvector/jenkins-slave

```

### Continue Jenkins setup. Configure Kubernetes Plugin

After installing `kubernetes-plugin` for Jenkins
* Go to Manage Jenkins | Bottom of Page | Cloud | Kubernetes (Add kubenretes cloud)
* Fill out plugin values
    * Name: kubernetes
    * Kubernetes URL: https://kubernetes.default:443
    * Kubernetes Namespace: jenkins
    * Credentials | Add | Jenkins (Choose Kubernetes service account option & Global + Save)
    * Test Connection | Should be successful! If not, check RBAC permissions and fix it!
    * Jenkins URL: http://jenkins
    * Tunnel : jenkins:50000
    * Apply cap only on alive pods : yes!
    * Add Kubernetes Pod Template
        * Name: jenkins-slave
        * Namespace: jenkins
        * Service Account: jenkins
        * Labels: jenkins-slave (you will need to use this label on all jobs)
        * Containers | Add Template
            * Name: jnlp
            * Docker Image: aimvector/jenkins-slave
            * Command to run : <Make this blank>
            * Arguments to pass to the command: <Make this blank>
            * Allocate pseudo-TTY: yes
            * Add Volume
                * HostPath type
                * HostPath: /var/run/docker.sock
                * Mount Path: /var/run/docker.sock
        * Timeout in seconds for Jenkins connection: 300
* Save

### CI/CD Pipeline.

```
pipeline {
    agent { 
        kubernetes{
            label 'jenkins-slave'
        }
        
    }
    environment{
        DOCKER_USERNAME = credentials('DOCKER_USERNAME')
        DOCKER_PASSWORD = credentials('DOCKER_PASSWORD')
    }
    stages {
        stage('docker login') {
            steps{
                sh('docker login -u $DOCKER_USERNAME -p $DOCKER_PASSWORD') 
            }
        }

        stage('git clone') {
            steps{
                sh(script: """
                    git clone https://github.com/OLG-MAN/project101-tf-eks-jenkins.git
                """, returnStdout: true) 
            }
        }

        stage('docker build') {
            steps{
                sh script: '''
                #!/bin/bash
                cd $WORKSPACE/project101-tf-eks-jenkins/python
                docker build . --network host -t olegan/testapp:${BUILD_NUMBER}
                '''
            }
        }

        stage('docker push') {
            steps{
                sh(script: """
                    docker push olegan/testapp:${BUILD_NUMBER}
                """)
            }
        }

        stage('deploy') {
            steps{
                sh script: '''
                #!/bin/bash
                cd $WORKSPACE/project101-tf-eks-jenkins/
                #get kubectl for this demo
                curl -LO https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl
                chmod +x ./kubectl
                ./kubectl apply -f ./kubernetes/configmaps/configmap.yaml
                ./kubectl apply -f ./kubernetes/secrets/secret.yaml
                cat ./kubernetes/deployments/deployment.yaml | sed s/10/${BUILD_NUMBER}/g | ./kubectl apply -f -
                ./kubectl apply -f ./kubernetes/services/service.yaml
                '''
        }
    }
}
}
```
-----------------------------------------