import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const sourceDir = path.resolve(__dirname, '../dist');
const targetDir = path.resolve(__dirname, '../../server/app/static');

if (!fs.existsSync(sourceDir)) {
  console.error(`[build:copy] Source build directory not found: ${sourceDir}`);
  process.exit(1);
}

// Ensure server static folder exists
if (!fs.existsSync(targetDir)) {
  fs.mkdirSync(targetDir, { recursive: true });
}

// Copy dist contents to server/app/static
fs.cpSync(sourceDir, targetDir, { recursive: true });
console.log(`[build:copy] Successfully copied client/dist to server/app/static`);

