# Deployment & Testing Guidelines

### 1. How do I test a GitHub Doc Healing Bot locally?

You need GitHub to send a message (a Webhook payload) to your laptop whenever a Pull Request is opened. But GitHub can't see your `localhost:8000`.

**The Solution: Use Ngrok (or LocalTunnel)**
Ngrok is a free developer tool that creates a secure public URL and routes it directly to your local machine.

* **Step 1:** Run your lightweight API locally (e.g., `uvicorn src.doc_healing.api.main:app --reload --port 8000`).
* **Step 2:** Run Ngrok in a separate terminal: `ngrok http 8000`. Ngrok will give you a public URL like `https://a1b2c3d4.ngrok.app`.
* **Step 3:** Go to a dummy GitHub test repository you created. Go to **Settings > Webhooks > Add webhook**. Paste the Ngrok URL (append your endpoint path, e.g., `/api/v1/webhook`).
* **Step 4:** Open a PR in your dummy repo. GitHub sends the payload to Ngrok, Ngrok forwards it to your local FastAPI server, and you can watch the entire extraction and validation process happen right in your terminal!

### 2. If AWS Bedrock provides the AI, can I test it locally?

**Yes, absolutely.** This is a very common misconception.

You do **not** need to run the AI model on your laptop, nor do you need to be deployed on an AWS server to use Bedrock. Amazon Bedrock is accessed via an API over the internet.

* As long as you have the AWS CLI installed on your laptop and have run `aws configure` to set up your hackathon credentials (Access Key and Secret Key), your local Python code can talk to Bedrock.
* When your local "Healing Engine" needs to fix code, your Python script uses the `boto3` library to send the prompt over the internet to AWS. AWS's massive servers process the Claude 3 model, generate the fix, and send the text back to your laptop. Your 8GB laptop barely breaks a sweat.

### 3. How do I enable the UI/Prototype to view changes?

Since you are building a backend-heavy system (a GitHub bot), you might not need a complex React frontend. The "UI" for the end-user is actually just the GitHub Pull Request interface (where your bot leaves a comment or pushes a commit).

However, to view the internal state for yourself and the hackathon judges, you have two lightweight options:

* **The Zero-Code UI (FastAPI Docs):** FastAPI automatically generates a UI at `http://localhost:8000/docs`. You can use this to manually trigger endpoints and see what your database is returning.
* **The Lightweight Dashboard (Streamlit):** If you want a nice dashboard to show the judges, create a 50-line Python script using [Streamlit](https://streamlit.io/). It runs locally and can easily read from your SQLite database to display charts of "PRs Validated," "Snippets Healed," and recent error logs. 
Streamlit or flask is fine

### 4. Once deployed on the AWS cloud, can I still make changes?

Yes. Deploying to the cloud is not a final, locked state; it's just moving your code to a computer that runs 24/7.

* **The Workflow:** You will continue to write code, test it locally using SQLite and Ngrok, and ensure it works perfectly.
* **The Update:** Once you are happy with the changes, you will push your updated Docker image to the AWS cloud (ECR/ECS) or redeploy your Lambda function. The cloud version will restart with your new features.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties across all configurations
- Unit tests validate specific examples, edge cases, and error conditions
- The implementation follows a bottom-up approach: configuration → abstraction → integration → deployment
