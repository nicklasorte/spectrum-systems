# Three Horizons Architecture Model

## Purpose
Large systems must plan at multiple distances simultaneously to avoid short-term hacks and speculative over-engineering. The three-horizon model keeps execution, architecture, and direction in balance so near-term delivery does not erode long-term intent.

## Horizon definitions
**H1 - Execution Horizon**  
Distance: 1-10 steps  
Focus:
- implement working components
- deliver executable functionality
- reduce friction in development
Examples:
- new engine prompts
- artifact parsers
- pipeline runners
- evaluation harnesses

**H2 - Architecture Horizon**  
Distance: 10-50 steps  
Focus:
- define interfaces
- stabilize contracts
- prevent structural mistakes
Examples:
- engine interface standard
- artifact envelope schema
- evidence bundle structure
- dependency graph

**H3 - Direction Horizon**  
Distance: 100-500 steps  
Focus:
- preserve system invariants
- guide ecosystem evolution
Examples:
- maturity model
- roadmap
- architectural decision records
- observability and evidence rules

## Core rule
Features are designed in Horizon 1, architecture is stabilized in Horizon 2, and system direction is governed in Horizon 3.

## Anti-patterns
- **Short-term trap**: Building only H1 features without H2 architecture.  
- **Speculation trap**: Designing H3 visions without executable H1 systems.  
- **Premature complexity**: Implementing H2 architecture before H1 use cases exist.  
