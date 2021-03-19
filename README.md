# project101-tf-eks-jenkins 
## Final task EPAM DevOps course winter 2020-2021

### Summary
* CI/CD project using provisioning EKS cluster through Terraform. 
* Deploy Jenkins to EKS through EFS. 
* Jenkins creating pod agents when CI/CD pipeline start and destroy it when pipeline finish.
* In pipeline we copy Github repo, build container from flask-app, push it to DockerHub and after delpoy to EKS cluster.

### Prepairing proccess
* Copy this repo to local host.
* Run and configure aws-cli container. 
* Install need tools for WSL and k8s cluster.

### Run work Container with Amazon CLI and conigure it

```
docker run -it --rm -v ${PWD}:/work -w /work --entrypoint /bin/sh amazon/aws-cli:latest
yum install -y jq gzip nano tar git curl wget
```

### Install kubectl, eksctl, terraform

```
# Install kubectl
curl -LO https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl
chmod +x ./kubectl && mv ./kubectl /usr/local/bin/kubectl

# Install eksctl
curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
mv /tmp/eksctl /usr/local/bin

# Install Terrform
yum install -y yum-utils
yum-config-manager --add-repo https://rpm.releases.hashicorp.com/AmazonLinux/hashicorp.repo
yum -y install terraform
```

### Configure AWS credentials and provisioning EKS cluster

```
# Configure your credentials from before created IAM account with all needed permissions
aws configure

# Init and Deploy Terraform infrastructure
terraform init
terraform apply

# Update kube config after EKS created.
aws eks update-kubeconfig --name CLUSTER_NAME --region eu-central-1
cp ~/.kube/config . 
```

### Setup our Cloud Storage 

```
# Deploy EFS storage driver
kubectl apply -k "github.com/kubernetes-sigs/aws-efs-csi-driver/deploy/kubernetes/overlays/stable/?ref=release-1.1"

# Get VPC_ID (and save it to txt file)
aws eks describe-cluster --name CLUSTER_NAME --query "cluster.resourcesVpcConfig.vpcId" --output text

# Get CIDR range (and save it to txt file)
aws ec2 describe-vpcs --vpc-ids VPC_ID --query "Vpcs[].CidrBlock" --output text

# Security for our instances to access file storage (and save sg-xxxxxxx to txt file)
aws ec2 create-security-group --description efs-test-sg --group-name efs-sg --vpc-id VPC_ID
aws ec2 authorize-security-group-ingress --group-id sg-xxxxxxx --protocol tcp --port 2049 --cidr VPC_CIDR

# Create storage
aws efs create-file-system --creation-token eks-efs

# Grab and Save FileSystemId to txt file and update our jenkins.pv.yaml
aws efs describe-file-systems --query "FileSystems[*].FileSystemId" --output text

# Create mount point (looking SUBNET_ID in created instance in EC2)
aws efs create-mount-target --file-system-id FS_ID --subnet-id SUBNET_ID --security-group GROUP_ID
```

### Setup our storage for Jenkins

```
# Create namespace check storage class
kubectl create ns jenkins
kubectl get storageclass

# Create volume (copy fs-xxxxxx to file jenkins.pv.yaml) and check it
kubectl apply -f ./jenkins/amazon-eks/jenkins.pv.yaml 
kubectl get pv

# Create volume claim and check it
kubectl apply -n jenkins -f ./jenkins/amazon-eks/jenkins.pvc.yaml
kubectl -n jenkins get pvc
```

### Deploy Jenkins

```
# Install RBAC and Deploy Jenkins check it
kubectl apply -n jenkins -f ./jenkins/jenkins.rbac.yaml 
kubectl apply -n jenkins -f ./jenkins/jenkins.deployment.yaml
kubectl -n jenkins get pods
```

### Create a service for Jenkins

```
kubectl apply -n jenkins -f ./jenkins/jenkins.service.yaml 
```

### Jenkins Initial Setup

```
# Grab password for Jenkins
kubectl -n jenkins exec -it POD_NAME cat /var/jenkins_home/secrets/initialAdminPassword

# Use type LoadBalancer in service and go to LoadBalancer DNS to configure Jenkins
kubectl -n jenkins get svc

### Second option is create service with type ClusterIP and make port forwarding
### kubectl port-forward -n jenkins POD_NAME 8080

# Setup user and recommended basic plugins
# Update jenkins after setup
```

#### ---optional step---
### SSH to our node to get Docker user info (Can skip this step - default docker UserID 1001 and GroupID 1950)

```
eval $(ssh-agent)
ssh-add ~/.ssh/id_rsa
ssh -i ~/.ssh/id_rsa ec2-user@ec2-YOUR_IP.YOUR_REGION.compute.amazonaws.com
id -u docker
cat /etc/group
# Get user ID for docker
# Get group ID for docker
```

#### ---optional step---
### Docker Jenkins Agent (Can create it or pull from DockerHub)

```
# you can build it
cd ./jenkins/dockerfiles/
docker build -t YOURNAME/jenkins-slave .
```

### Continue Jenkins setup. Configure Kubernetes Plugin

* Installing `kubernetes-plugin` for Jenkins and restart
* Go to Manage Jenkins | Manage Nodes and Clouds | Configure Cloud | Kubernetes (Add kubernetes cloud) | Details
* Fill out plugin values
    * Name: kubernetes
    * Kubernetes URL: https://kubernetes.default:443
    * Kubernetes Namespace: jenkins
    * Credentials | Add | Jenkins (Choose Kubernetes service account option & Global + Save)
    * Test Connection | Should be successful! If not, check RBAC permissions and fix it!
    * Jenkins URL: http://jenkins
    * Tunnel : jenkins:50000
    * Add Kubernetes Pod Template
        * Name: jenkins-slave | templates details
        * Namespace: jenkins
        * Labels: jenkins-slave (you will need to use this label on all jobs)
        * Add Containers | Add Container Template
            * Name: jnlp
            * Docker Image: aimvector/jenkins-slave
            * Command to run : <Make this blank>
            * Arguments to pass to the command: <Make this blank>
            * Allocate pseudo-TTY: yes
            * Advanced | User ID : 1001 | GroupID : 1950
            * Add Volume
                * HostPath type
                * HostPath: /var/run/docker.sock
                * Mount Path: /var/run/docker.sock
                * in Bottom of Page | 
                * Service Account : jenkins 
                * User ID : 1001 
                * GroupID : 1950
* Save

### Make credentials for DockerHub
* Go to Manage Jenkins | Credentials | click near "domain global" | add credentials
* Select kind : secret text 
    * Secret : YOUR_DOCKER_HUB_USERNAME
    * ID : DOCKER_USERNAME 
* save
* Make second credentials
* Select kind : secret text 
    * Secret : YOUR_DOCKER_HUB_PASSWORD
    * ID : DOCKER_PASSWORD
* save

### CI/CD Pipeline.
* Create new item in Jenkins (type pipeline) and copy code below to pipeline.
* Make Github webhook trigger.
* Save.
* Click "Build now" or push to Github repo to pipeline start.

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

### Check all components of k8s cluster

```
#Check our deployment
kubectl -n jenkins get deploy -owide
#Check our pods
kubectl -n jenkins get pods
#Check services
kubectl -n jenkins get svc
```

### Copy DNS from "example-service" and paste to browser. Check working web app.

### Add domain name to our EKS cluster
* Register free domain like web-a.pp.ua
* Create hosted zone in Route 53 with same address name
* Change NS in domain registrator to Route53 Hosted Zone NS
* Create record - address alias to Cluster LoadBalancer
* After 15-20 min registerred address start working. (Can check status in https://www.whatsmydns.net/)
-----------------------------------------

#### References

Video

1. https://www.youtube.com/watch?v=eqOCdNO2Nmk
2. https://www.youtube.com/watch?v=Qy2A_yJH5-o
3. https://www.youtube.com/watch?v=QThadS3Soig

Articles

1. https://learn.hashicorp.com/tutorials/terraform/eks?in=terraform/kubernetes
2. https://aws.amazon.com/blogs/storage/deploying-jenkins-on-amazon-eks-with-amazon-efs/
3. https://aws.amazon.com/blogs/opensource/continuous-integration-using-jenkins-and-hashicorp-terraform-on-amazon-eks/

Python Web App

https://github.com/dibashthapa/Flask-Ecommerce

Project presentation

[Here](https://github.com/OLG-MAN/project101-tf-eks-jenkins/blob/main/CI_CD_task.pdf)
