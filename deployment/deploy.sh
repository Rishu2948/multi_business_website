#!/bin/bash

# Deployment Script for Multi-Business Bakery Platform
# This script handles local development deployment and testing

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="multi-business-bakery"
ENVIRONMENT="${1:-development}"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${NC}ℹ $1${NC}"
}

# Function to check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed"
        exit 1
    fi
    print_success "AWS CLI is installed"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    print_success "Docker is installed"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed"
        exit 1
    fi
    print_success "Python 3 is installed"
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials are not configured"
        exit 1
    fi
    print_success "AWS credentials are configured"
    
    echo ""
}

# Function to deploy backend infrastructure
deploy_backend_infrastructure() {
    print_info "Deploying backend infrastructure..."
    
    STACK_NAME="${PROJECT_NAME}-${ENVIRONMENT}-backend"
    
    # Check if stack exists
    if aws cloudformation describe-stacks --stack-name $STACK_NAME &> /dev/null; then
        print_info "Stack exists, updating..."
        aws cloudformation deploy \
            --template-file deployment/cloudformation/backend-infrastructure.yaml \
            --stack-name $STACK_NAME \
            --parameter-overrides \
                Environment=$ENVIRONMENT \
                ProjectName=$PROJECT_NAME \
                VpcId=$VPC_ID \
                PrivateSubnet1=$PRIVATE_SUBNET_1 \
                PrivateSubnet2=$PRIVATE_SUBNET_2 \
                PublicSubnet1=$PUBLIC_SUBNET_1 \
                PublicSubnet2=$PUBLIC_SUBNET_2 \
            --capabilities CAPABILITY_IAM \
            --no-fail-on-empty-changeset
    else
        print_info "Stack does not exist, creating..."
        aws cloudformation deploy \
            --template-file deployment/cloudformation/backend-infrastructure.yaml \
            --stack-name $STACK_NAME \
            --parameter-overrides \
                Environment=$ENVIRONMENT \
                ProjectName=$PROJECT_NAME \
                VpcId=$VPC_ID \
                PrivateSubnet1=$PRIVATE_SUBNET_1 \
                PrivateSubnet2=$PRIVATE_SUBNET_2 \
                PublicSubnet1=$PUBLIC_SUBNET_1 \
                PublicSubnet2=$PUBLIC_SUBNET_2 \
            --capabilities CAPABILITY_IAM
    fi
    
    print_success "Backend infrastructure deployed"
    echo ""
}

# Function to deploy auth infrastructure
deploy_auth_infrastructure() {
    print_info "Deploying auth infrastructure..."
    
    STACK_NAME="${PROJECT_NAME}-${ENVIRONMENT}-auth-infrastructure"
    
    # Check if stack exists
    if aws cloudformation describe-stacks --stack-name $STACK_NAME &> /dev/null; then
        print_info "Stack exists, updating..."
        aws cloudformation deploy \
            --template-file deployment/cloudformation/auth-infrastructure.yaml \
            --stack-name $STACK_NAME \
            --parameter-overrides \
                Environment=$ENVIRONMENT \
                ProjectName=$PROJECT_NAME \
                RedisEnabled=false \
            --capabilities CAPABILITY_IAM \
            --no-fail-on-empty-changeset
    else
        print_info "Stack does not exist, creating..."
        aws cloudformation deploy \
            --template-file deployment/cloudformation/auth-infrastructure.yaml \
            --stack-name $STACK_NAME \
            --parameter-overrides \
                Environment=$ENVIRONMENT \
                ProjectName=$PROJECT_NAME \
                RedisEnabled=false \
            --capabilities CAPABILITY_IAM
    fi
    
    print_success "Auth infrastructure deployed"
    echo ""
}

# Function to build and push Docker image
build_and_push_image() {
    print_info "Building Docker image..."
    
    cd backend
    docker build -t ${PROJECT_NAME}-backend:latest .
    print_success "Docker image built"
    
    print_info "Tagging image for ECR..."
    ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    docker tag ${PROJECT_NAME}-backend:latest ${ECR_REGISTRY}/${PROJECT_NAME}-backend:latest
    print_success "Image tagged"
    
    print_info "Logging in to ECR..."
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY
    print_success "Logged in to ECR"
    
    print_info "Pushing image to ECR..."
    docker push ${ECR_REGISTRY}/${PROJECT_NAME}-backend:latest
    print_success "Image pushed to ECR"
    
    cd ..
    echo ""
}

# Function to deploy to ECS
deploy_to_ecs() {
    print_info "Deploying to ECS..."
    
    CLUSTER_NAME="${PROJECT_NAME}-${ENVIRONMENT}-cluster"
    SERVICE_NAME="${PROJECT_NAME}-backend"
    
    # Get current task definition
    TASK_DEF=$(aws ecs describe-task-definition \
        --task-definition ${PROJECT_NAME}-${ENVIRONMENT}-backend \
        --query 'taskDefinition' \
        --output json)
    
    # Update image
    ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    TASK_DEF=$(echo $TASK_DEF | jq \
        --arg image "$ECR_REGISTRY/${PROJECT_NAME}-backend:latest" \
        '.containerDefinitions[0].image = $image')
    
    # Register new task definition
    NEW_TASK_DEF=$(aws ecs register-task-definition \
        --cli-input-json "$TASK_DEF" \
        --query 'taskDefinition.taskDefinitionArn' \
        --output text)
    
    print_success "New task definition registered: $NEW_TASK_DEF"
    
    # Update service
    aws ecs update-service \
        --cluster $CLUSTER_NAME \
        --service $SERVICE_NAME \
        --task-definition $NEW_TASK_DEF \
        --force-new-deployment
    
    print_success "Service updated"
    
    # Wait for deployment to complete
    print_info "Waiting for deployment to stabilize..."
    aws ecs wait services-stable \
        --cluster $CLUSTER_NAME \
        --services $SERVICE_NAME
    
    print_success "Deployment completed successfully"
    echo ""
}

# Function to run auth migrations
run_auth_migrations() {
    print_info "Running auth migrations..."
    
    cd backend
    
    # Get MongoDB connection string from environment or parameter
    if [ -z "$MONGO_URL" ]; then
        print_warning "MONGO_URL not set, using SSM parameter..."
        MONGO_URL=$(aws ssm get-parameter \
            --name "/${PROJECT_NAME}/${ENVIRONMENT}/mongodb/url" \
            --query 'Parameter.Value' \
            --output text)
    fi
    
    if [ -z "$DB_NAME" ]; then
        print_warning "DB_NAME not set, using SSM parameter..."
        DB_NAME=$(aws ssm get-parameter \
            --name "/${PROJECT_NAME}/${ENVIRONMENT}/mongodb/db_name" \
            --query 'Parameter.Value' \
            --output text)
    fi
    
    export MONGO_URL=$MONGO_URL
    export DB_NAME=$DB_NAME
    
    print_info "Running MFA migration report..."
    python3 scripts/mfa_migration.py --report
    
    print_success "Auth migrations completed"
    cd ..
    echo ""
}

# Function to revoke legacy sessions
revoke_legacy_sessions() {
    print_info "Revoking legacy sessions..."
    
    cd backend
    
    # Get MongoDB connection string
    if [ -z "$MONGO_URL" ]; then
        MONGO_URL=$(aws ssm get-parameter \
            --name "/${PROJECT_NAME}/${ENVIRONMENT}/mongodb/url" \
            --query 'Parameter.Value' \
            --output text)
    fi
    
    if [ -z "$DB_NAME" ]; then
        DB_NAME=$(aws ssm get-parameter \
            --name "/${PROJECT_NAME}/${ENVIRONMENT}/mongodb/db_name" \
            --query 'Parameter.Value' \
            --output text)
    fi
    
    export MONGO_URL=$MONGO_URL
    export DB_NAME=$DB_NAME
    
    print_info "Checking legacy session statistics..."
    python3 scripts/revoke_legacy_sessions.py --stats
    
    read -p "Do you want to revoke legacy sessions? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        python3 scripts/revoke_legacy_sessions.py --force
        print_success "Legacy sessions revoked"
        
        # Update SSM parameter
        aws ssm put-parameter \
            --name "/${PROJECT_NAME}/${ENVIRONMENT}/auth/config" \
            --value '{"mfa_enforce_for_admins":"false","auth_accept_legacy_session":"false","auth_rate_limit_per_minute":"10","webhook_skip_verify":"false","max_sessions_per_user":"5","access_token_ttl_seconds":"900","refresh_token_ttl_seconds":"604800"}' \
            --type String \
            --overwrite
        
        print_success "AUTH_ACCEPT_LEGACY_SESSION updated to false"
    else
        print_warning "Legacy session cutover cancelled"
    fi
    
    cd ..
    echo ""
}

# Function to run security sweep
run_security_sweep() {
    print_info "Running security sweep..."
    
    # Get API endpoint
    API_ENDPOINT=$(aws cloudformation describe-stacks \
        --stack-name ${PROJECT_NAME}-${ENVIRONMENT}-backend \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
        --output text)
    
    cd backend
    python3 scripts/sweep_privileged_apis.py --url $API_ENDPOINT
    cd ..
    
    print_success "Security sweep completed"
    echo ""
}

# Function to show help
show_help() {
    echo "Usage: ./deploy.sh [command] [environment]"
    echo ""
    echo "Commands:"
    echo "  all                    Deploy everything (infrastructure + code)"
    echo "  backend-infra         Deploy backend infrastructure only"
    echo "  auth-infra            Deploy auth infrastructure only"
    echo "  build                 Build and push Docker image"
    echo "  deploy               Deploy to ECS"
    echo "  migrations           Run auth migrations"
    echo "  revoke-sessions      Revoke legacy sessions (cutover)"
    echo "  security-sweep       Run security sweep"
    echo "  help                 Show this help message"
    echo ""
    echo "Environments:"
    echo "  development           (default)"
    echo "  staging"
    echo "  production"
    echo ""
    echo "Examples:"
    echo "  ./deploy.sh all staging"
    echo "  ./deploy.sh migrations production"
    echo "  ./deploy.sh revoke-sessions staging"
}

# Main script logic
main() {
    COMMAND="${1:-help}"
    ENVIRONMENT="${2:-development}"
    
    print_info "Multi-Business Bakery Deployment"
    print_info "Environment: $ENVIRONMENT"
    print_info "Command: $COMMAND"
    echo ""
    
    check_prerequisites
    
    case $COMMAND in
        all)
            deploy_backend_infrastructure
            deploy_auth_infrastructure
            build_and_push_image
            deploy_to_ecs
            run_auth_migrations
            ;;
        backend-infra)
            deploy_backend_infrastructure
            ;;
        auth-infra)
            deploy_auth_infrastructure
            ;;
        build)
            build_and_push_image
            ;;
        deploy)
            deploy_to_ecs
            ;;
        migrations)
            run_auth_migrations
            ;;
        revoke-sessions)
            revoke_legacy_sessions
            ;;
        security-sweep)
            run_security_sweep
            ;;
        help)
            show_help
            ;;
        *)
            print_error "Unknown command: $COMMAND"
            show_help
            exit 1
            ;;
    esac
    
    print_success "Deployment completed successfully!"
}

# Run main function
main "$@"
