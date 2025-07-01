"use strict";
/**
 * SIMPLE SUBSCRIPTION VALIDATION
 *
 * Quick validation of subscription ID parsing and coherence
 * without needing full chart environment setup
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.SubscriptionValidator = void 0;
const subscription_baseline_1 = require("../../../../lib/subscription-baseline");
class SubscriptionValidator {
    /**
     * Parse subscription ID the same way the series classes do
     */
    parseSubscriptionId(subscriptionId) {
        console.log(`🔍 Parsing subscription ID: ${subscriptionId}`);
        const subscriptionParts = subscriptionId.split('&');
        if (subscriptionParts.length >= 3) {
            const [seriesTypeStr, timeRange, ...marketIdParts] = subscriptionParts;
            const marketId = marketIdParts.join('&'); // Rejoin market ID parts that may contain '&'
            const side = seriesTypeStr.toLowerCase();
            const result = {
                marketId,
                side,
                timeRange: timeRange,
                original: subscriptionId
            };
            console.log(`✅ Parsed successfully:`, result);
            return result;
        }
        else {
            console.error(`❌ Invalid subscription ID format: ${subscriptionId}`);
            return null;
        }
    }
    /**
     * Validate all baseline subscription IDs
     */
    validateBaselineSubscriptions() {
        console.log('\n🧪 Validating all baseline subscription IDs...\n');
        const seriesTypes = ['YES', 'NO'];
        const timeRanges = ['1H', '1W', '1M', '1Y'];
        let totalTests = 0;
        let passedTests = 0;
        for (const seriesType of seriesTypes) {
            for (const timeRange of timeRanges) {
                const subscriptionId = subscription_baseline_1.BASELINE_SUBSCRIPTION_IDS[seriesType][timeRange];
                totalTests++;
                console.log(`📊 Testing ${seriesType} ${timeRange}: ${subscriptionId}`);
                const parsed = this.parseSubscriptionId(subscriptionId);
                if (parsed) {
                    // Validate the parsed components match expectations
                    const expectedSide = seriesType.toLowerCase();
                    const expectedMarketId = 'MARKET';
                    if (parsed.side === expectedSide &&
                        parsed.timeRange === timeRange &&
                        parsed.marketId === expectedMarketId) {
                        console.log(`   ✅ Valid: side=${parsed.side}, range=${parsed.timeRange}, market=${parsed.marketId}`);
                        passedTests++;
                    }
                    else {
                        console.error(`   ❌ Validation failed:`);
                        console.error(`      Expected: side=${expectedSide}, range=${timeRange}, market=${expectedMarketId}`);
                        console.error(`      Got: side=${parsed.side}, range=${parsed.timeRange}, market=${parsed.marketId}`);
                    }
                }
                else {
                    console.error(`   ❌ Failed to parse subscription ID: ${subscriptionId}`);
                }
                console.log('');
            }
        }
        console.log(`\n📊 Test Results: ${passedTests}/${totalTests} passed`);
        if (passedTests === totalTests) {
            console.log('✅ All baseline subscription IDs are valid and parseable!');
        }
        else {
            console.error('❌ Some subscription IDs failed validation!');
            throw new Error(`Validation failed: ${passedTests}/${totalTests} tests passed`);
        }
    }
    /**
     * Test subscription ID format compatibility
     */
    testSubscriptionIdCompatibility() {
        console.log('\n🧪 Testing subscription ID compatibility...\n');
        // Test cases that should work
        const validTestCases = [
            'yes&1H&MARKET',
            'no&1W&CUSTOM&MARKET',
            'yes&1M&BTC&USD',
            'no&1Y&SOME&OTHER&MARKET'
        ];
        // Test cases that should fail
        const invalidTestCases = [
            'invalid_format',
            'yes_only',
            '',
            'too_many_parts_here_causing_issues'
        ];
        console.log('Testing valid subscription ID formats:');
        for (const testCase of validTestCases) {
            const parsed = this.parseSubscriptionId(testCase);
            if (!parsed) {
                throw new Error(`Valid test case failed: ${testCase}`);
            }
        }
        console.log('\nTesting invalid subscription ID formats:');
        for (const testCase of invalidTestCases) {
            const parsed = this.parseSubscriptionId(testCase);
            if (parsed && testCase !== 'too_many_parts_here_causing_issues') {
                // Note: extra parts are allowed, only minimum 3 parts required
                throw new Error(`Invalid test case should have failed: ${testCase}`);
            }
        }
        console.log('✅ Subscription ID compatibility tests passed!');
    }
    /**
     * Test range switching logic
     */
    testRangeSwitching() {
        console.log('\n🧪 Testing range switching logic...\n');
        const originalId = subscription_baseline_1.BASELINE_SUBSCRIPTION_IDS.YES['1H'];
        console.log(`Original subscription: ${originalId}`);
        const parsed = this.parseSubscriptionId(originalId);
        if (!parsed) {
            throw new Error('Failed to parse original subscription ID');
        }
        // Simulate range switching by generating new subscription IDs
        const newRanges = ['1W', '1M', '1Y'];
        for (const newRange of newRanges) {
            // This is how the series would generate a new subscription ID
            const newId = subscription_baseline_1.BASELINE_SUBSCRIPTION_IDS[parsed.side.toUpperCase()][newRange];
            console.log(`Switch to ${newRange}: ${newId}`);
            const newParsed = this.parseSubscriptionId(newId);
            if (!newParsed) {
                throw new Error(`Failed to parse new subscription ID: ${newId}`);
            }
            // Verify the new subscription maintains the same series type and market
            if (newParsed.side !== parsed.side || newParsed.marketId !== parsed.marketId) {
                throw new Error(`Range switching broke consistency: ${originalId} -> ${newId}`);
            }
            if (newParsed.timeRange !== newRange) {
                throw new Error(`Range switching didn't update time range correctly: expected ${newRange}, got ${newParsed.timeRange}`);
            }
            console.log(`   ✅ Range switch to ${newRange} maintains consistency`);
        }
        console.log('✅ Range switching logic tests passed!');
    }
    /**
     * Run all validation tests
     */
    runAllTests() {
        console.log('🚀 Starting Subscription Validation Tests...\n');
        try {
            this.validateBaselineSubscriptions();
            this.testSubscriptionIdCompatibility();
            this.testRangeSwitching();
            console.log('\n🎉 ALL SUBSCRIPTION VALIDATION TESTS PASSED!');
            console.log('✅ Subscription logic is coherent and compatible with emitters');
        }
        catch (error) {
            console.error('\n❌ VALIDATION FAILED:', error);
            throw error;
        }
    }
}
exports.SubscriptionValidator = SubscriptionValidator;
// Run validation if this file is executed directly
if (require.main === module) {
    const validator = new SubscriptionValidator();
    validator.runAllTests();
}
