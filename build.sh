#!/bin/bash
set -e

echo "Building React frontend..."
cd frontend
npm install
npm run build
cd ..

echo "Copying build to backend/static..."
rm -rf backend/static
cp -r frontend/build backend/static

echo "Build complete."
