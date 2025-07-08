import { DefaultParserFactory } from '../ParserFactory'
import { KalshiParser } from '../KalshiParser'
import { PolymarketParser } from '../PolymarketParser'
import { Platform } from '../../types'

describe('DefaultParserFactory', () => {
  let factory: DefaultParserFactory

  beforeEach(() => {
    factory = new DefaultParserFactory()
  })

  describe('createParser', () => {
    it('should create KalshiParser for kalshi platform', () => {
      const parser = factory.createParser('kalshi')
      
      expect(parser).toBeInstanceOf(KalshiParser)
      expect(parser.platform).toBe('kalshi')
    })

    it('should create PolymarketParser for polymarket platform', () => {
      const parser = factory.createParser('polymarket')
      
      expect(parser).toBeInstanceOf(PolymarketParser)
      expect(parser.platform).toBe('polymarket')
    })

    it('should return the same instance for repeated calls', () => {
      const parser1 = factory.createParser('kalshi')
      const parser2 = factory.createParser('kalshi')
      
      expect(parser1).toBe(parser2)
    })

    it('should throw error for unsupported platform', () => {
      expect(() => {
        factory.createParser('unsupported' as Platform)
      }).toThrow('Parser not found for platform: unsupported')
    })

    it('should handle both platforms independently', () => {
      const kalshiParser = factory.createParser('kalshi')
      const polymarketParser = factory.createParser('polymarket')
      
      expect(kalshiParser).toBeInstanceOf(KalshiParser)
      expect(polymarketParser).toBeInstanceOf(PolymarketParser)
      expect(kalshiParser).not.toBe(polymarketParser)
    })
  })

  describe('parser instances', () => {
    it('should initialize with parsers for all supported platforms', () => {
      const kalshiParser = factory.createParser('kalshi')
      const polymarketParser = factory.createParser('polymarket')
      
      expect(kalshiParser).toBeDefined()
      expect(polymarketParser).toBeDefined()
    })
  })
})