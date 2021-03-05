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

### Install kubectl, eksctl, terraform Grab configures (later)
```
# kubectl
curl -LO https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl
chmod +x ./kubectl && mv ./kubectl /usr/local/bin/kubectl

# eksctl
curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
mv /tmp/eksctl /usr/local/bin

# update kube config after EKS created.
aws eks update-kubeconfig --name getting-started-eks --region eu-central-1
cp ~/.kube/config .

# terraform install
yum install -y yum-utils
```

### Configure AWS credentials and provisioning EKS cluster
```
# Configure your credenrtials from before created IAM account with all needed permissions
aws configure
# Init and deploy
terraform init
terraform apply
```
