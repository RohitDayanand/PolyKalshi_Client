"use strict";
/**
 * SUBSCRIPTION BASELINE CONFIGURATION
 *
 * Comprehensive subscription ID mapping for all time ranges and series types.
 * This provides consistent subscription IDs across the entire application.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.ALL_SUBSCRIPTION_IDS = exports.SUBSCRIPTION_REGISTRY = exports.BASELINE_SUBSCRIPTION_IDS = exports.RANGE_CACHE_SIZES = exports.RANGE_UPDATE_FREQUENCIES = exports.MARKET_SYMBOLS = void 0;
exports.generateSubscriptionId = generateSubscriptionId;
exports.generateBaselineSubscriptionConfigs = generateBaselineSubscriptionConfigs;
exports.getSubscriptionConfig = getSubscriptionConfig;
// Base symbols for different markets
exports.MARKET_SYMBOLS = {
    DEFAULT: 'MARKET',
    STOCK: 'AAPL',
    CRYPTO: 'BTC',
    FOREX: 'EURUSD',
};
// Update frequency mapping per time range (in milliseconds)
exports.RANGE_UPDATE_FREQUENCIES = {
    '1H': 1000, // 1 second - high frequency for day trading
    '1W': 5000, // 5 seconds - medium frequency for weekly
    '1M': 30000, // 30 seconds - lower frequency for monthly
    '1Y': 300000, // 5 minutes - lowest frequency for yearly
};
// Cache size mapping per time range
exports.RANGE_CACHE_SIZES = {
    '1H': 1440, // 24 hours * 60 minutes = 1440 points (1 per minute)
    '1W': 672, // 7 days * 24 hours * 4 = 672 points (1 per 15 minutes)
    '1M': 720, // 30 days * 24 = 720 points (1 per hour)
    '1Y': 365, // 365 days = 365 points (1 per day)
};
/**
 * Generate subscription ID for a specific series type, range, and symbol
 */
function generateSubscriptionId(seriesType, range, symbol = exports.MARKET_SYMBOLS.DEFAULT) {
    return `${seriesType.toLowerCase()}_${range}_${symbol}`;
}
/**
 * BASELINE SUBSCRIPTION IDS
 * All possible combinations for the default market
 */
exports.BASELINE_SUBSCRIPTION_IDS = {
    YES: {
        '1H': generateSubscriptionId('YES', '1H'),
        '1W': generateSubscriptionId('YES', '1W'),
        '1M': generateSubscriptionId('YES', '1M'),
        '1Y': generateSubscriptionId('YES', '1Y'),
    },
    NO: {
        '1H': generateSubscriptionId('NO', '1H'),
        '1W': generateSubscriptionId('NO', '1W'),
        '1M': generateSubscriptionId('NO', '1M'),
        '1Y': generateSubscriptionId('NO', '1Y'),
    }
};
/**
 * Generate all subscription configurations for baseline setup
 */
function generateBaselineSubscriptionConfigs() {
    const configs = [];
    const ranges = ['1H', '1W', '1M', '1Y'];
    const types = ['YES', 'NO'];
    for (const range of ranges) {
        for (const type of types) {
            configs.push({
                id: generateSubscriptionId(type, range),
                updateFrequency: exports.RANGE_UPDATE_FREQUENCIES[range],
                historyLimit: exports.RANGE_CACHE_SIZES[range],
                seriesType: type,
                range: range,
                symbol: exports.MARKET_SYMBOLS.DEFAULT
            });
        }
    }
    return configs;
}
/**
 * Get subscription config for specific series type and range
 */
function getSubscriptionConfig(seriesType, range) {
    return {
        id: generateSubscriptionId(seriesType, range),
        updateFrequency: exports.RANGE_UPDATE_FREQUENCIES[range],
        historyLimit: exports.RANGE_CACHE_SIZES[range],
        seriesType,
        range,
        symbol: exports.MARKET_SYMBOLS.DEFAULT
    };
}
/**
 * COMPREHENSIVE SUBSCRIPTION REGISTRY
 * All subscription IDs that should be available
 */
exports.SUBSCRIPTION_REGISTRY = {
    // Default market subscriptions
    ...exports.BASELINE_SUBSCRIPTION_IDS,
    // Stock market subscriptions (AAPL)
    STOCK: {
        YES: {
            '1H': generateSubscriptionId('YES', '1H', exports.MARKET_SYMBOLS.STOCK),
            '1W': generateSubscriptionId('YES', '1W', exports.MARKET_SYMBOLS.STOCK),
            '1M': generateSubscriptionId('YES', '1M', exports.MARKET_SYMBOLS.STOCK),
            '1Y': generateSubscriptionId('YES', '1Y', exports.MARKET_SYMBOLS.STOCK),
        },
        NO: {
            '1H': generateSubscriptionId('NO', '1H', exports.MARKET_SYMBOLS.STOCK),
            '1W': generateSubscriptionId('NO', '1W', exports.MARKET_SYMBOLS.STOCK),
            '1M': generateSubscriptionId('NO', '1M', exports.MARKET_SYMBOLS.STOCK),
            '1Y': generateSubscriptionId('NO', '1Y', exports.MARKET_SYMBOLS.STOCK),
        }
    },
    // Crypto market subscriptions (BTC)
    CRYPTO: {
        YES: {
            '1H': generateSubscriptionId('YES', '1H', exports.MARKET_SYMBOLS.CRYPTO),
            '1W': generateSubscriptionId('YES', '1W', exports.MARKET_SYMBOLS.CRYPTO),
            '1M': generateSubscriptionId('YES', '1M', exports.MARKET_SYMBOLS.CRYPTO),
            '1Y': generateSubscriptionId('YES', '1Y', exports.MARKET_SYMBOLS.CRYPTO),
        },
        NO: {
            '1H': generateSubscriptionId('NO', '1H', exports.MARKET_SYMBOLS.CRYPTO),
            '1W': generateSubscriptionId('NO', '1W', exports.MARKET_SYMBOLS.CRYPTO),
            '1M': generateSubscriptionId('NO', '1M', exports.MARKET_SYMBOLS.CRYPTO),
            '1Y': generateSubscriptionId('NO', '1Y', exports.MARKET_SYMBOLS.CRYPTO),
        }
    }
};
// Export flattened list of all subscription IDs for easy iteration
exports.ALL_SUBSCRIPTION_IDS = Object.values(exports.BASELINE_SUBSCRIPTION_IDS)
    .flatMap(typeIds => Object.values(typeIds));
console.log('📋 Subscription Baseline - Generated IDs:', exports.ALL_SUBSCRIPTION_IDS);
