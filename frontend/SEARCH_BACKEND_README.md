# Market Search Backend Documentation

## Overview
This document explains how to customize the search functionality to populate the search bar with your own questions and logic.

## Architecture

### Components
1. **Frontend**: `components/market-search.tsx` - The search bar component
2. **API Layer**: `app/api/search/route.ts` - Next.js API route handling search requests
3. **Service Layer**: `lib/search-service.ts` - Your custom search logic implementation
4. **Configuration**: `app/api/search/config/route.ts` - Dynamic configuration management

## How to Customize Your Search Logic

### 1. Basic Search Customization

Edit the `lib/search-service.ts` file to implement your custom logic:

```typescript
// In MarketSearchService class

async searchPolymarketQuestions(query: string): Promise<Market[]> {
  // Replace this with your actual implementation:
  
  // Option 1: Connect to external APIs
  const apiResults = await fetch(`https://your-api.com/search?q=${query}`)
  const data = await apiResults.json()
  
  // Option 2: Database queries
  const dbResults = await yourDatabase.query('SELECT * FROM markets WHERE title LIKE ?', [`%${query}%`])
  
  // Option 3: Custom business logic
  const customResults = await this.generateCustomQuestions(query)
  
  return this.formatResults(customResults)
}
```

### 2. Advanced Configuration

You can customize search behavior by updating the configuration:

```typescript
// Update search configuration
const customConfig = {
  maxResults: 15,
  enableFuzzySearch: true,
  includeCategories: ['Politics', 'Economics', 'Technology'],
  minVolumeThreshold: 5000
}

// Via API call
fetch('/api/search/config', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(customConfig)
})
```

### 3. Question Generation Templates

Customize the question templates in `generatePolymarketQuestions()` and `generateKalshiQuestions()`:

```typescript
private async generatePolymarketQuestions(query: string): Promise<Market[]> {
  const questionTemplates = [
    `Will ${query} succeed by end of 2025?`,
    `${query}: Market sentiment prediction`,
    `Will ${query} outperform expectations?`,
    // Add your custom templates here
  ]
  
  // Your custom logic here
}
```

### 4. Custom Ranking Algorithm

Implement your own relevance scoring in `calculateRelevanceScore()`:

```typescript
private calculateRelevanceScore(title: string, query: string): number {
  // Your custom scoring algorithm
  // Consider factors like:
  // - Keyword matching
  // - Popularity scores
  // - Recency
  // - User preferences
  // - Market volume
  
  return relevanceScore
}
```

## API Endpoints

### Search Endpoint
- **URL**: `/api/search`
- **Method**: GET
- **Parameters**: 
  - `platform`: "polymarket" | "kalshi"
  - `query`: string
- **Response**:
```json
{
  "success": true,
  "data": [...markets],
  "platform": "polymarket",
  "query": "election",
  "timestamp": "2025-05-28T..."
}
```

### Configuration Endpoint
- **URL**: `/api/search/config`
- **Methods**: GET, POST
- **GET Response**:
```json
{
  "success": true,
  "data": {
    "maxResults": 20,
    "enableFuzzySearch": true,
    "includeCategories": ["Politics", "Economics"],
    "minVolumeThreshold": 1000
  }
}
```

## Integration Examples

### 1. Connect to External API

```typescript
async searchPolymarketQuestions(query: string): Promise<Market[]> {
  try {
    const response = await fetch(`https://polymarket-api.com/markets?search=${encodeURIComponent(query)}`)
    const apiData = await response.json()
    
    return apiData.markets.map(market => ({
      id: market.id,
      title: market.question,
      category: market.category,
      volume: market.volume,
      price: market.price,
      platform: 'polymarket' as const
    }))
  } catch (error) {
    console.error('API integration error:', error)
    return []
  }
}
```

### 2. Database Integration

```typescript
import { db } from '@/lib/database' // Your database connection

async searchKalshiQuestions(query: string): Promise<Market[]> {
  const results = await db.query(`
    SELECT id, title, category, volume, liquidity 
    FROM kalshi_markets 
    WHERE title ILIKE $1 
    ORDER BY volume DESC 
    LIMIT $2
  `, [`%${query}%`, this.config.maxResults])
  
  return results.rows.map(row => ({
    id: row.id,
    title: row.title,
    category: row.category,
    volume: row.volume,
    liquidity: row.liquidity,
    platform: 'kalshi' as const
  }))
}
```

### 3. Machine Learning Integration

```typescript
async searchMarkets(platform: string, query: string): Promise<Market[]> {
  // Use ML for query understanding
  const enhancedQuery = await this.enhanceQueryWithML(query)
  
  // Generate semantically similar questions
  const similarQuestions = await this.generateSimilarQuestions(enhancedQuery)
  
  // Rank using ML model
  const rankedResults = await this.rankWithML(similarQuestions, query)
  
  return rankedResults
}
```

## Testing Your Implementation

1. Start the development server:
```bash
npm run dev
```

2. Test the search API directly:
```bash
curl "http://localhost:3000/api/search?platform=polymarket&query=election"
```

3. Test configuration updates:
```bash
curl -X POST "http://localhost:3000/api/search/config" \
  -H "Content-Type: application/json" \
  -d '{"maxResults": 10, "minVolumeThreshold": 5000}'
```

## Performance Considerations

1. **Caching**: Implement caching for frequently searched queries
2. **Rate Limiting**: Add rate limiting to prevent abuse
3. **Async Processing**: Use background jobs for complex search operations
4. **Database Indexing**: Ensure proper indexing for database searches

## Error Handling

The system includes comprehensive error handling:
- API validation errors
- Network timeout handling
- Graceful fallbacks
- User-friendly error messages

## Next Steps

1. Replace the mock implementations with your actual search logic
2. Connect to your preferred data sources (APIs, databases, etc.)
3. Implement custom ranking algorithms
4. Add authentication if needed
5. Set up monitoring and analytics

For questions or support, refer to the main project documentation.
