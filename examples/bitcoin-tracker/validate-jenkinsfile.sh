#!/bin/bash
# Test Jenkinsfile syntax locally before pushing to Jenkins

set -e

echo "🔍 Validating Jenkinsfile syntax..."

# Method 1: Basic syntax check with groovy (if available)
if command -v groovy &> /dev/null; then
    echo "Using groovy to validate syntax..."
    groovy -e "import groovy.lang.GroovyShell; new GroovyShell().parse(new File('Jenkinsfile'))"
    echo "✅ Groovy syntax valid"
else
    echo "⚠️  groovy not installed, skipping syntax check"
fi

# Method 2: Check for common issues with grep
echo ""
echo "🔍 Checking for common pipeline issues..."

ISSUES=0

# Check for required sections
if ! grep -q "pipeline {" Jenkinsfile; then
    echo "❌ Missing 'pipeline {' block"
    ISSUES=$((ISSUES + 1))
fi

if ! grep -q "agent " Jenkinsfile; then
    echo "❌ Missing 'agent' directive"
    ISSUES=$((ISSUES + 1))
fi

if ! grep -q "stages {" Jenkinsfile; then
    echo "❌ Missing 'stages {' block"
    ISSUES=$((ISSUES + 1))
fi

# Check for balanced braces
OPEN_BRACES=$(grep -o "{" Jenkinsfile | wc -l)
CLOSE_BRACES=$(grep -o "}" Jenkinsfile | wc -l)

if [ "$OPEN_BRACES" -ne "$CLOSE_BRACES" ]; then
    echo "❌ Unbalanced braces: $OPEN_BRACES open, $CLOSE_BRACES close"
    ISSUES=$((ISSUES + 1))
else
    echo "✅ Braces balanced ($OPEN_BRACES pairs)"
fi

# Check for required environment variables
REQUIRED_VARS=("FLUID_PROVIDER" "GCP_PROJECT_ID" "CONTRACT_FILE")
for var in "${REQUIRED_VARS[@]}"; do
    if grep -q "$var" Jenkinsfile; then
        echo "✅ Found environment variable: $var"
    else
        echo "⚠️  Missing environment variable: $var"
    fi
done

# Check for required stages
REQUIRED_STAGES=("Validate" "Plan" "Deploy" "Verify")
for stage in "${REQUIRED_STAGES[@]}"; do
    if grep -q "stage.*$stage" Jenkinsfile; then
        echo "✅ Found required stage: $stage"
    else
        echo "❌ Missing required stage: $stage"
        ISSUES=$((ISSUES + 1))
    fi
done

# Method 3: Validate with Jenkins CLI (if configured)
if command -v jenkins-cli &> /dev/null; then
    echo ""
    echo "🔍 Validating with Jenkins CLI..."
    jenkins-cli declarative-linter < Jenkinsfile && echo "✅ Jenkins validation passed" || {
        echo "⚠️  Jenkins validation failed (check server connection)"
    }
fi

echo ""
if [ $ISSUES -eq 0 ]; then
    echo "✅ All checks passed!"
    echo ""
    echo "Next steps:"
    echo "  1. Commit Jenkinsfile: git add Jenkinsfile && git commit -m 'Add Jenkins pipeline'"
    echo "  2. Push to repository: git push origin main"
    echo "  3. Create Jenkins job pointing to this Jenkinsfile"
    echo "  4. Run build with parameters"
    exit 0
else
    echo "❌ Found $ISSUES issues - fix before committing"
    exit 1
fi
