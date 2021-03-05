# project101-tf-eks-jenkins
Summary
CI/CD project using provisioning EKS cluster through Terraform. 
Deploy Jenkins to EKS through EFS. 
Jenkins creating pod agents when CI/CD pipeline start and destroy it when pipeline finish.
In pipeline we build container from app in repo push it to docker hub and after delpoy to EKS cluster.

