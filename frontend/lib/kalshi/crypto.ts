/**
 * Cryptographic utilities for Kalshi API authentication
 */

import { KALSHI_CRYPTO_CONFIG } from './constants';

/**
 * Creates a RSASSA-PSS signature for Kalshi API authentication
 * @param message - The message to sign
 * @param privateKeyPem - The private key in PEM format
 * @returns Base64 encoded signature
 */
export async function signPssText(message: string, privateKeyPem: string): Promise<string> {
  // Check if Web Crypto API is available
  if (typeof crypto === 'undefined' || !crypto.subtle) {
    throw new Error('Web Crypto API is not available. This client requires a secure context (HTTPS) and modern browser support.');
  }

  try {
    // Import the private key
    const privateKey = await importPrivateKey(privateKeyPem);
    
    // Convert message to ArrayBuffer
    const messageBuffer = new TextEncoder().encode(message);
    
    // Sign the message using RSASSA-PSS
    const signatureBuffer = await crypto.subtle.sign(
      {
        name: KALSHI_CRYPTO_CONFIG.SIGNATURE_ALGORITHM,
        saltLength: KALSHI_CRYPTO_CONFIG.SALT_LENGTH,
      },
      privateKey,
      messageBuffer
    );
    
    // Convert to base64
    return arrayBufferToBase64(signatureBuffer);
  } catch (error) {
    throw new Error(`RSA sign PSS failed: ${error}`);
  }
}

/**
 * Imports a private key from PEM format
 * @param privateKeyPem - The private key in PEM format
 * @returns CryptoKey for signing
 */
async function importPrivateKey(privateKeyPem: string): Promise<CryptoKey> {
  // Remove PEM headers and whitespace
  const pemContents = privateKeyPem
    .replace(/-----BEGIN PRIVATE KEY-----/, '')
    .replace(/-----END PRIVATE KEY-----/, '')
    .replace(/-----BEGIN RSA PRIVATE KEY-----/, '')
    .replace(/-----END RSA PRIVATE KEY-----/, '')
    .replace(/\s/g, '');
  
  // Convert base64 to ArrayBuffer
  const keyData = base64ToArrayBuffer(pemContents);
  
  try {
    // Try PKCS#8 format first
    return await crypto.subtle.importKey(
      'pkcs8',
      keyData,
      {
        name: KALSHI_CRYPTO_CONFIG.SIGNATURE_ALGORITHM,
        hash: KALSHI_CRYPTO_CONFIG.HASH_ALGORITHM,
      },
      false,
      ['sign']
    );
  } catch (error) {
    // If PKCS#8 fails, the key might be in PKCS#1 format
    // In a real implementation, you'd need to convert PKCS#1 to PKCS#8
    // For now, throw a helpful error
    throw new Error(
      'Private key import failed. Ensure the key is in PKCS#8 format. ' +
      'Convert PKCS#1 keys using: openssl pkcs8 -topk8 -inform PEM -outform PEM -nocrypt -in key.pem -out key_pkcs8.pem'
    );
  }
}

/**
 * Converts base64 string to ArrayBuffer
 * @param base64 - Base64 string
 * @returns ArrayBuffer
 */
function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binaryString = atob(base64);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes.buffer;
}

/**
 * Converts ArrayBuffer to base64 string
 * @param buffer - ArrayBuffer
 * @returns Base64 string
 */
function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * Generates authentication headers for Kalshi API requests
 * @param method - HTTP method (GET, POST, etc.)
 * @param path - API path
 * @param keyId - Kalshi API key ID
 * @param privateKeyPem - Private key in PEM format
 * @returns Headers object with authentication
 */
export async function generateAuthHeaders(
  method: string,
  path: string,
  keyId: string,
  privateKeyPem: string
): Promise<Record<string, string>> {
  const timestamp = Date.now().toString();
  
  // Extract path without query parameters for signature
  const pathParts = path.split('?');
  const pathForSignature = pathParts[0];
  
  // Create message string for signature
  const messageString = timestamp + method + pathForSignature;
  
  // Sign the message
  const signature = await signPssText(messageString, privateKeyPem);
  
  return {
    'KALSHI-ACCESS-KEY': keyId,
    'KALSHI-ACCESS-SIGNATURE': signature,
    'KALSHI-ACCESS-TIMESTAMP': timestamp,
  };
}
