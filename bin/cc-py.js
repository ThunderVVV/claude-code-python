#!/usr/bin/env node
/**
 * cc-py - CC Code Python TUI
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

function getBinaryPath() {
  const platform = process.platform;
  const arch = process.arch;
  
  const binaryName = 'cc-py';
  
  const platformDir = path.join(__dirname, '..', 'binary', `${platform}-${arch}`);
  const binaryPath = path.join(platformDir, binaryName);
  
  if (fs.existsSync(binaryPath)) {
    return binaryPath;
  }
  
  const fallbackPath = path.join(__dirname, '..', 'binary', binaryName);
  if (fs.existsSync(fallbackPath)) {
    return fallbackPath;
  }
  
  return null;
}

function run() {
  const binaryPath = getBinaryPath();
  
  if (!binaryPath) {
    console.error('Error: cc-py binary not found.');
    console.error('Please reinstall: npm install -g cc-py');
    process.exit(1);
  }
  
  const child = spawn(binaryPath, process.argv.slice(2), {
    stdio: 'inherit',
    env: process.env,
  });
  
  child.on('error', (err) => {
    console.error('Failed to start cc-py:', err.message);
    process.exit(1);
  });
  
  child.on('exit', (code, signal) => {
    if (signal) {
      process.exit(128 + (signal === 'SIGTERM' ? 15 : signal === 'SIGKILL' ? 9 : 0));
    } else {
      process.exit(code || 0);
    }
  });
}

run();
