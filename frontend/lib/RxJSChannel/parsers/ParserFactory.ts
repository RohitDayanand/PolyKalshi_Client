import { Platform } from '../types'
import { PlatformParser, ParserFactory } from './types'
import { KalshiParser } from './KalshiParser'
import { PolymarketParser } from './PolymarketParser'

export class DefaultParserFactory implements ParserFactory {
  private parsers = new Map<Platform, PlatformParser>()

  constructor() {
    this.parsers.set('kalshi', new KalshiParser())
    this.parsers.set('polymarket', new PolymarketParser())
  }

  createParser(platform: Platform): PlatformParser {
    const parser = this.parsers.get(platform)
    
    if (!parser) {
      throw new Error(`Parser not found for platform: ${platform}`)
    }
    
    return parser
  }
}