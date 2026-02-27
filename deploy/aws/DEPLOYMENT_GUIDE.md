# Final AWS Deployment Steps

Here is the exact step-by-step process you need to follow to get everything running in your AWS environment.

## Part 1: AWS Infrastructure Provisioning

You need to run the setup script I created to create your AWS resources (Database, Redis, Load Balancer, etc.).

1. **Open your terminal locally** (ensuring you have the AWS CLI installed and configured with your account `122610498241`).
2. **Find your VPC and Subnet IDs**:
   - Go to the AWS Console -> VPC -> Your VPCs. Copy your Default VPC ID (e.g., `vpc-01234abcd`).
   - Go to Subnets. Copy two subnet IDs from that VPC (e.g., `subnet-1111` and `subnet-2222`).
   - Go to EC2 -> Security Groups. Copy the Default Security Group ID (e.g., `sg-abcdef`).
3. **Update the setup script**:
   - Open `deploy/aws/setup_infrastructure.sh`.
   - Replace the placeholders (`VPC_ID`, `SUBNET_IDS`, `SECURITY_GROUP`) at the top of the file with the IDs you just copied.
4. **Run the script**:
   ```bash
   chmod +x deploy/aws/setup_infrastructure.sh
   ./deploy/aws/setup_infrastructure.sh
   ```
   *Note: This will take a few minutes as AWS provisions the PostgreSQL database and Redis cluster.*

## Part 2: Setting up AWS Secrets Manager

Once the script finishes, your database and Redis queue will be running. We need to securely store their connection URLs so your application can read them.

1. **Get the Database Endpoint**: Go to AWS Console -> RDS -> Databases. Click on `doc-healing-db`. Look for the "Endpoint" under "Connectivity & security".
2. **Get the Redis Endpoint**: Go to AWS Console -> ElastiCache -> Redis clusters. Click on `doc-healing-redis`. Look for the "Primary Endpoint".
3. **Create the Secrets file locally**:
   Create a new file called `secrets.json` on your computer (do NOT commit this to Git). Paste this inside, replacing the endpoints:
   ```json
   {
     "DATABASE_URL": "postgresql://postgres:YourSecurePassword123!@<YOUR_RDS_ENDPOINT>:5432/postgres",
     "REDIS_HOST": "<YOUR_REDIS_ENDPOINT>",
     "REDIS_PORT": "6379",
     "GITHUB_WEBHOOK_SECRET": "your_github_webhook_secret_here"
   }
   ```
4. **Upload to AWS**:
   Run this command in your terminal to save the secrets securely in AWS:
   ```bash
   aws secretsmanager create-secret --name doc-healing/production/secrets --secret-string file://secrets.json
   ```

## Part 3: Generating AWS Access Keys

Before GitHub can talk to AWS, you need to create an Access Key for your user.

1. **Go to your AWS Console**.
2. Search for **IAM** (Identity and Access Management) in the top search bar and click on it.
3. In the left sidebar, click on **Users**.
4. Click on your user account (e.g., `Pooja Patel` or whichever user you are logged in as).
   - *Note: This user must have AdministratorAccess or sufficient permissions to manage ECR, ECS, and SecretsManager.*
5. Click on the **Security credentials** tab.
6. Scroll down to the **Access keys** section and click **Create access key**.
7. Select **Command Line Interface (CLI)** or **Third-party service** as the use case. Check the confirmation box and click **Next**.
8. Click **Create access key**.
9. You will now see your **Access key ID** and **Secret access key**. Copy both of these values immediately and store them somewhere safe (you will not be able to see the secret key again later).

## Part 4: How to add Secrets in GitHub

For GitHub Actions to be able to build your code and push it to AWS automatically, it needs permission to talk to your AWS account.

1. **Go to your GitHub Repository** in your web browser.
2. Click on the **Settings** tab.
3. In the left sidebar, scroll down to **Secrets and variables** and click on **Actions**.
4. Click the green **New repository secret** button.
5. Add your AWS Access Key ID:
   - **Name**: `AWS_ACCESS_KEY_ID`
   - **Secret**: *(Paste your AWS Access Key ID here)*
   - Click **Add secret**.
6. Click **New repository secret** again.
7. Add your AWS Secret Access Key:
   - **Name**: `AWS_SECRET_ACCESS_KEY`
   - **Secret**: *(Paste your AWS Secret Access Key here)*
   - Click **Add secret**.

Once these two secrets are saved in GitHub, the `.github/workflows/deploy.yml` pipeline we created will automatically trigger when you push to the `main` branch. It will use those credentials to log into AWS, build your Docker image, push it to ECR, and deploy it to your ECS cluster!
