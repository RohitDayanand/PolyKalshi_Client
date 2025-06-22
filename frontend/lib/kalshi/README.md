# Kalshi TypeScript Client

A modern TypeScript client for the Kalshi API using RxJS and WebSocketSubject, ported from the Python implementation.

## Features

- **RxJS-based**: Uses Observables for reactive programming patterns
- **WebSocket Support**: Real-time market data streaming using RxJS WebSocketSubject
- **TypeScript**: Full type safety with comprehensive type definitions
- **Authentication**: RSASSA-PSS signature-based authentication using Web Crypto API
- **Rate Limiting**: Built-in request rate limiting and retry logic
- **Reconnection**: Automatic WebSocket reconnection with configurable retry policies
- **Browser Compatible**: Works in modern browsers with secure contexts (HTTPS)

## Architecture

### Core Components

1. **Types** (`types.ts`): Comprehensive TypeScript type definitions
2. **Constants** (`constants.ts`): API endpoints, configuration, and default values
3. **Crypto** (`crypto.ts`): Cryptographic utilities for API authentication
4. **HTTP Client** (`http-client.ts`): REST API client with RxJS integration
5. **WebSocket Client** (`websocket-client.ts`): Real-time streaming client using WebSocketSubject
6. **Main Client** (`client.ts`): Combined HTTP and WebSocket client interface
7. **React Hooks** (`hooks.ts`): React integration hooks (for React applications)

### Key Improvements Over Python Version

- **Reactive Streams**: Uses RxJS Observables instead of async/await callbacks
- **Type Safety**: Full TypeScript typing with compile-time error checking
- **Modern APIs**: Uses Web Crypto API instead of external crypto libraries
- **Browser Ready**: Designed for browser environments with fallbacks
- **Composable**: Modular design allows using HTTP-only or WebSocket-only clients

## Configuration

### Constants Setup

Update the constants in `constants.ts`:

```typescript
export const KALSHI_API_CONFIG = {
  DEMO: {
    KEY_ID: 'your-demo-key-id-here',
    PRIVATE_KEY_PATH: './rsa_kalshi_key.txt', // Path to private key file
  },
  PROD: {
    KEY_ID: 'your-prod-key-id-here', 
    PRIVATE_KEY_PATH: './rsa_kalshi_key.txt', // Path to private key file
  }
} as const;
```

### Basic Usage

```typescript
import { KalshiClient, Environment } from '@/lib/kalshi';

const client = new KalshiClient({
  environment: Environment.DEMO,
  keyId: 'your-api-key',
  privateKey: 'your-private-key-pem-string'
});

// Connect to WebSocket
client.connect().subscribe(() => {
  console.log('Connected to Kalshi WebSocket');
});

// Subscribe to market data
client.subscribeToOrderbook('PRESWIN24').subscribe(() => {
  console.log('Subscribed to orderbook');
});

// Listen to orderbook updates
client.orderbookDeltas.subscribe(delta => {
  console.log('Orderbook update:', delta);
});
```

## API Methods

### HTTP Client Methods

- `getBalance()`: Get account balance
- `getExchangeStatus()`: Get exchange status
- `getTrades(options)`: Get trade history
- `get<T>(path, params)`: Generic GET request
- `post<T>(path, body)`: Generic POST request

### WebSocket Client Methods

- `connect()`: Establish WebSocket connection
- `disconnect()`: Close WebSocket connection
- `subscribe(subscription)`: Subscribe to data streams
- `unsubscribe(subscription)`: Unsubscribe from data streams

### Data Streams

- `messages`: All incoming WebSocket messages
- `orderbookSnapshots`: Full orderbook snapshots
- `orderbookDeltas`: Orderbook updates
- `trades`: Trade executions
- `fills`: Order fills
- `tickers`: Price ticker updates
- `errors`: Error messages

## Requirements

- **Browser**: Modern browser with Web Crypto API support (HTTPS required)
- **Node.js**: Version 16+ (if using in Node.js environment)
- **Dependencies**: RxJS 7+, TypeScript 4.5+

## Security Notes

1. **Private Keys**: Never expose private keys in client-side code in production
2. **HTTPS Required**: Web Crypto API requires secure context (HTTPS)
3. **Environment Variables**: Use environment variables for sensitive configuration
4. **Key Format**: Private keys must be in PKCS#8 format (convert PKCS#1 if needed)

## Error Handling

The client includes comprehensive error handling:

- `KalshiError`: Base error class
- `KalshiAuthError`: Authentication failures
- `KalshiRateLimitError`: Rate limit exceeded
- `KalshiWebSocketError`: WebSocket connection issues

## Rate Limiting

Built-in rate limiting prevents API throttling:

- Default: 100ms between requests
- Configurable: Set custom rate limits per client
- Retry Logic: Automatic retry with exponential backoff

## Known Issues

1. **Private Key Loading**: File-based key loading only works in Node.js environments
2. **Web Crypto API**: Requires HTTPS in production environments
3. **PKCS#1 Keys**: Must be converted to PKCS#8 format
4. **Browser Compatibility**: Requires modern browser with full ES2020+ support

## Migration from Python

The TypeScript client provides equivalent functionality to the Python version:

- **KalshiHttpClient** → `KalshiHttpClient` class
- **KalshiWebSocketClient** → `KalshiWebSocketClient` class  
- **Callbacks** → RxJS Observables and reactive streams
- **Async/Await** → Observable subscriptions with operators
- **Error Handling** → Typed error classes with RxJS error handling

This implementation provides a modern, type-safe, and reactive approach to Kalshi API integration.
