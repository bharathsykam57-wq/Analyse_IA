#!/bin/bash
# Railway Deployment Guide for Analyse_IA
# This script provides a checklist and commands for deploying to Railway

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   ANALYSE_IA RAILWAY DEPLOYMENT GUIDE${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo ""

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo -e "${YELLOW}Railway CLI not found. Install with:${NC}"
    echo -e "  npm i -g @railway/cli"
    exit 1
fi

echo -e "${GREEN}✓${NC} Railway CLI found"

# Step 1: Generate JWT Secret
echo ""
echo -e "${BLUE}[Step 1] Generate JWT Secret${NC}"
echo "Generate a secure random token for JWT_SECRET_KEY:"
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
echo -e "${GREEN}✓${NC} JWT_SECRET_KEY: $(echo $JWT_SECRET | cut -c1-20)..."
echo ""
echo "Copy this value to Railway dashboard:"
echo -e "${YELLOW}${JWT_SECRET}${NC}"
echo ""

# Step 2: Check current project
echo -e "${BLUE}[Step 2] Railway Project Status${NC}"
echo "Current directory: $(pwd)"
echo ""
echo "Checking Railway project..."
railway status 2>/dev/null || {
    echo -e "${YELLOW}Not in a Railway project yet.${NC}"
    echo "Run: railway init"
    exit 1
}
echo -e "${GREEN}✓${NC} Project configured"

# Step 3: Environment variables checklist
echo ""
echo -e "${BLUE}[Step 3] Required Environment Variables${NC}"
echo -e "${YELLOW}Set these in Railway dashboard (Project → Variables):${NC}"
echo ""
cat << 'EOF'
Required:
  □ JWT_SECRET_KEY          [Generated above]
  □ DATABASE_URL            [Supabase PostgreSQL URL]
  □ REDIS_URL               [Upstash Redis URL]
  □ CORS_ORIGINS            [https://your-domain.com]
  □ ENVIRONMENT             production
  □ LLM_PROVIDER            groq
  □ GROQ_API_KEY            [Your Groq API key]

Optional:
  □ UPLOAD_DIR              /tmp/uploads
  □ LOG_LEVEL               info
  □ LANGFUSE_PUBLIC_KEY     [For monitoring]
  □ LANGFUSE_SECRET_KEY     [For monitoring]

EOF

read -p "Have you set all required environment variables in Railway? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Please set environment variables in Railway dashboard first${NC}"
    exit 1
fi

# Step 4: Deploy services
echo ""
echo -e "${BLUE}[Step 4] Deploy Backend Service${NC}"
echo "Deploying FastAPI backend..."
railway service add backend --template=python
# or: cd backend && railway service add --name analyse-ia-backend

# Step 5: Deploy worker
echo ""
echo -e "${BLUE}[Step 5] Deploy Celery Worker${NC}"
echo "Deploying Celery worker..."
railway service add worker --template=python
# Configure: python -m celery -A backend.api.celery.worker worker --loglevel=info

# Step 6: Run migrations
echo ""
echo -e "${BLUE}[Step 6] Database Migrations${NC}"
echo "Running database migrations..."
echo ""
echo "Add release command to backend service:"
echo "  Build Command: pip install -r requirements/production.txt"
echo "  Start Command: uvicorn backend.api.main:app --host 0.0.0.0 --port \$PORT"
echo "  Release Command: alembic upgrade head"
echo ""

read -p "Have you set the release command? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Set release command in Railway dashboard:${NC}"
    echo "  Backend Service → Settings → Release Command"
    echo "  Command: alembic upgrade head"
    exit 1
fi

# Step 7: Deploy frontend
echo ""
echo -e "${BLUE}[Step 7] Deploy Frontend (Vercel or Netlify)${NC}"
echo "Create frontend/.env.production.local with:"
echo "  NEXT_PUBLIC_API_URL=https://your-backend.railway.app/api/v1"
echo ""
echo "Then deploy to Vercel/Netlify with same environment variable"
echo ""

# Step 8: Run tests
echo ""
echo -e "${BLUE}[Step 8] Run Production Tests${NC}"
echo "After deployment, verify with:"
echo ""
echo -e "${YELLOW}1. Authentication Tests:${NC}"
echo "   python tests/test_production_auth.py --backend-url https://your-backend.railway.app"
echo ""
echo -e "${YELLOW}2. File Upload Tests:${NC}"
echo "   python tests/test_production_uploads.py --backend-url https://your-backend.railway.app --auth-token <token>"
echo ""
echo -e "${YELLOW}3. Celery Queue Tests:${NC}"
echo "   python tests/test_production_celery.py --backend-url https://your-backend.railway.app --auth-token <token>"
echo ""

# Summary
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}DEPLOYMENT CHECKLIST${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo ""
cat << 'EOF'
□ Step 1: Generate JWT_SECRET_KEY
   Command: python -c "import secrets; print(secrets.token_urlsafe(32))"

□ Step 2: Create Railway project
   Command: railway init

□ Step 3: Set environment variables in Railway dashboard
   - JWT_SECRET_KEY (from Step 1)
   - DATABASE_URL (PostgreSQL with pgvector)
   - REDIS_URL (Redis connection)
   - CORS_ORIGINS (your production domain)
   - LLM provider credentials

□ Step 4: Add backend service
   Command: railway service add backend

□ Step 5: Add Celery worker service
   Command: railway service add worker

□ Step 6: Configure release command
   Backend Service → Settings → Release Command
   Command: alembic upgrade head

□ Step 7: Deploy frontend
   - Create frontend/.env.production.local
   - Deploy to Vercel/Netlify

□ Step 8: Verify deployment
   - Check Railway logs for errors
   - Run production tests (see Step 8 above)
   - Test authentication flow
   - Test file uploads
   - Test Celery tasks

□ Step 9: Monitor in production
   - Railway dashboard logs
   - Error tracking (Sentry)
   - LLM monitoring (Langfuse)

EOF

echo ""
echo -e "${GREEN}✓${NC} Deployment guide complete!"
echo ""
echo "For detailed instructions, see: PRODUCTION_SETUP.md"
echo ""

# Optional: Link to Railway
read -p "Link current project to Railway? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    railway link
    echo -e "${GREEN}✓${NC} Project linked to Railway"
fi
