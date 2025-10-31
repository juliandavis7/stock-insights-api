# Stock Analysis API - Claude Skill

This directory contains comprehensive documentation for the Stock Analysis API backend as a Claude skill.

## What's in This Skill?

Complete reference documentation for a FastAPI-based stock analysis API with:
- Clerk JWT authentication
- FMP & yfinance API integration
- Financial metrics calculations
- Multi-year projections
- Optimized for 300 FMP API calls/minute

## Documentation Structure

### Main Entry Point
- **SKILL.md** - Start here! Overview, quick reference, common tasks

### Detailed References
- **references/endpoints.md** - All API endpoints with request/response examples
- **references/auth.md** - Clerk JWT authentication implementation
- **references/rate-limiting.md** - SlowAPI rate limiting setup and strategy
- **references/models.md** - All Pydantic request/response models
- **references/external-apis.md** - FMP and yfinance integration details
- **references/database.md** - Database information (future planning)

### Scripts
- **scripts/setup_api.sh** - Development environment setup script

## Quick Start

1. **Read SKILL.md first** - Get oriented with the project
2. **Check references/** - Dive into specific areas as needed
3. **Run setup script** - Set up your development environment

```bash
# Make executable (if not already)
chmod +x scripts/setup_api.sh

# Run setup
./scripts/setup_api.sh
```

## Using This Skill with Claude

This skill helps Claude understand and work with:
- API endpoint implementation patterns
- Clerk authentication flow
- Rate limiting strategies
- FMP API integration and optimization
- Financial calculations and projections
- Pydantic model definitions

## Documentation Philosophy

- **Actual Code**: Uses real code from the repository, not pseudocode
- **Complete Examples**: Full request/response examples for all endpoints
- **Practical Focus**: Emphasizes common tasks and patterns
- **Cross-Referenced**: Links between related documentation
- **No Sensitive Data**: All API keys and secrets removed

## Project Context

**Repository**: stock-insights-api  
**Framework**: FastAPI 0.104+  
**Python**: 3.9+  
**Authentication**: Clerk JWT tokens  
**External APIs**: FMP (primary), yfinance (supplementary)  
**FMP Tier**: Starter (300 calls/minute)

## Key Optimizations

The API has been optimized to reduce FMP API usage:
- `/metrics`: 6 calls per request (reduced from 8)
- `/financials`: 2 calls per request (reduced from 3)
- `/charts`: 3 calls per request (already optimal)
- Total savings: ~25% reduction in API calls

## Common Use Cases

### For Adding New Endpoints
See: references/endpoints.md

### For Authentication Issues
See: references/auth.md

### For Rate Limiting
See: references/rate-limiting.md

### For External API Integration
See: references/external-apis.md

### For Request/Response Models
See: references/models.md

## Maintenance

This documentation should be updated when:
- New endpoints are added
- Authentication changes
- Rate limiting strategy changes
- External API integrations change
- Pydantic models are modified

## Contributing

When updating this skill:
1. Use actual code from the repository
2. Include complete, working examples
3. Remove sensitive information
4. Update cross-references
5. Test code examples
6. Keep under 300 lines per file

## Support

For questions or issues:
1. Check SKILL.md for overview
2. Review relevant reference file
3. Check actual code in repository
4. Test with local development setup

---

**Last Updated**: October 31, 2025  
**Version**: 1.0.0

