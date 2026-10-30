# Complete Render Deployment Guide (Coaching Management System)

This guide walks you through deploying your **Coaching Management System** to **Render.com** with **MongoDB Atlas** for free, persistent cloud hosting.

---

## Step 1: Set Up Free Cloud MongoDB (MongoDB Atlas)

Since Render's free tier containers are stateless, a persistent cloud database is required. MongoDB Atlas provides a **100% Free Forever M0 cluster**:

1. Go to **[mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas)** and sign up or sign in.
2. Click **Create a Deployment** and choose the **M0 Free** cluster tier (select AWS or Google Cloud, and pick a region close to you like Mumbai, Singapore, or Frankfurt).
3. **Set Up Database Access**:
   - Create a database user (e.g., username: `coaching_admin`, password: `YourStrongPassword123`).
   - *Save this password for later.*
4. **Set Up Network Access**:
   - Go to **Network Access** in the left sidebar.
   - Click **Add IP Address** > select **Allow Access from Anywhere (`0.0.0.0/0`)** > **Confirm**. *(This is required so Render's cloud servers can connect to your database).*
5. **Get Your Connection String**:
   - Go to **Database** > click **Connect**.
   - Select **Drivers** (Python).
   - Copy the connection string. It will look like:
     ```
     mongodb+srv://coaching_admin:<password>@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority
     ```
   - Replace `<password>` with your real password, and add `/coaching_db` before the `?`:
     ```
     mongodb+srv://coaching_admin:YourStrongPassword123@cluster0.abcde.mongodb.net/coaching_db?retryWrites=true&w=majority
     ```

---

## Step 2: Push Code to GitHub

Render deploys directly from your GitHub repository.

1. Go to **[github.com](https://github.com)** and create a new repository (e.g. `coaching-management-system`, set to **Private** or **Public**).
2. If you have Git installed on your PC:
   ```powershell
   cd "C:\Users\kuldeep rajput\.gemini\antigravity\scratch\coaching-management-system"
   git init
   git add .
   git commit -m "Initial commit of Coaching Management System"
   git branch -M main
   git remote add origin https://github.com/<your-username>/coaching-management-system.git
   git push -u origin main
   ```
   *(Or if using **GitHub Desktop**, click **File > Add Local Repository**, select `C:\Users\kuldeep rajput\.gemini\antigravity\scratch\coaching-management-system`, and click **Publish Repository**).*

---

## Step 3: Create Web Service on Render

1. Go to **[render.com](https://render.com)** and sign in with GitHub.
2. On your Render Dashboard, click the blue **New +** button in the top right, then select **Web Service**.
3. Choose **Build and deploy from a Git repository** > click **Next**.
4. Select your `coaching-management-system` repository.
5. Fill in the service details:
   - **Name**: `coaching-management-system` (or your preferred name)
   - **Region**: Singapore, Frankfurt, or Ohio (pick one close to you)
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**:
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command**:
     ```bash
     gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120 app:app
     ```
   - **Instance Type**: Select **Free**.

---

## Step 4: Configure Environment Variables on Render

Scroll down to the **Environment Variables** section on Render and click **Add Environment Variable** for each:

| Key | Value | Description |
| :--- | :--- | :--- |
| `PYTHON_VERSION` | `3.11.9` | Python runtime version |
| `FLASK_DEBUG` | `False` | Production mode |
| `SECRET_KEY` | `your-secure-random-32-char-key` | Session encryption key |
| `MONGO_URI` | `mongodb+srv://coaching_admin:...` | Your MongoDB Atlas connection string |
| `DB_NAME` | `coaching_db` | Database name |
| `DEFAULT_ADMIN_USERNAME` | `admin` | Initial admin username |
| `DEFAULT_ADMIN_PASSWORD` | `YourAdminPassword123` | Initial admin password |
| `DEFAULT_ADMIN_NAME` | `Admin Principal` | Admin display name |

---

## Step 5: Deploy & Access Your Live Web App

1. Click **Deploy Web Service** at the bottom of the page.
2. Render will build the project, install dependencies via `pip`, and start Gunicorn.
3. Once the build log displays `Your service is live 🎉`, click the URL at the top:
   **`https://coaching-management-system.onrender.com`**
4. Log in with your admin credentials:
   - **Username**: `admin`
   - **Password**: `<The password you set in DEFAULT_ADMIN_PASSWORD>`

Your coaching academy is now running live on the internet with automatic SSL (HTTPS)!
