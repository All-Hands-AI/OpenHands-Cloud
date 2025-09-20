# OpenHands Enterprise Release Process Proposal

## 1. Introduction

This document proposes a structured release process and support policy for
OpenHands Enterprise, addressing current gaps in our release cadence, versioning
strategy, and customer support expectations.

### 1.1 Problem Statement

OpenHands Enterprise currently lacks:

1. **Established Release Process**: No defined release cadence or standardized
   process for OpenHands Enterprise (Helm charts)
2. **Technical Coordination Challenges**: Complex dependencies between multiple
   components:
   - Enterprise container (OpenHands core)
   - Runtime API container and Helm chart
   - Image loader container and chart
   - Runtimes container
3. **Version Management Issues**:
   - No clear tagging convention linking Helm chart releases to OpenHands core
     releases
   - Component versions are tracked via Git SHAs in workflow files, making them
     difficult to parse and understand
   - No readable mapping between SaaS releases and Enterprise releases
4. **Undefined Support Policy**: No established support policy for Enterprise
   customers, creating uncertainty around:
   - Which versions receive bug fixes and security updates
   - How long versions are supported
   - Customer upgrade expectations and timelines

### 1.2 Proposed Solution

#### 1.2.1 Establish Release Support Policy & Enterprise Release Cadence

**Recommended Policy**:

- **Enterprise releases weekly, staggered 1 week behind SaaS** to allow
  validation
- **Support current release + previous 2 releases** (3 total supported versions)
- **Current release**: Full bug fixes and security updates
- **Previous 2 releases**: Security fixes only
- **Older releases**: No support - customers must upgrade

This approach balances rapid delivery with enterprise stability needs while
limiting support burden. See Section 2.2 for alternative options and Section 3
for technical implementation details.

#### 1.2.2 Automate Release Process

**Unified Versioning Strategy**:

- **All components use identical semantic version numbers** (e.g., v1.2.3)
- **Synchronized releases** across all repositories and artifacts:
  - OpenHands Enterprise Helm chart: v1.2.3
  - Runtime API container & chart: v1.2.3
  - Image Loader container & chart: v1.2.3
  - Runtimes container: v1.2.3
- **Automated coordination** eliminates manual Git SHA tracking in workflow
  files
- **Single source of truth** for version compatibility

This replaces the current system of tracking component versions via Git SHAs in
workflow files with a clear, automated process where all components share the
same version number for each release.

### 1.3 Additional Context

#### 1.3.1 Enterprise Customer Change Management

Enterprise customers operate under different constraints than SaaS users, and
understanding these patterns is critical for designing an effective release
strategy.

**Two Classes of Enterprise Customers**:

**Traditional/Slow-Moving Enterprises**:

- **Update Frequency**: Semi-annual or quarterly updates only
- **Change Process**: Extensive corporate approval, change tickets, designated
  change windows
- **Industry Constraints**:
  - Insurance: November blackouts during open enrollment periods
  - Retail: Restricted changes during holiday shopping seasons
- **Support Expectations**: Long support windows, extensive backporting demands
- **Risk Profile**: Highly risk-averse, prefer stability over new features

**Forward-Leaning/Fast-Moving Enterprises**:

- **Update Frequency**: Weekly or monthly updates with proper change management
- **Change Process**: Streamlined approval processes, standard change windows
- **Infrastructure**: Cloud-native, containerized environments with image
  quarantine processes
- **Support Expectations**: Willing to stay current in exchange for high-quality
  releases
- **Risk Profile**: Accept faster pace if release quality is consistently high

#### 1.3.2 Current Customer Reality

**Important Note**: Our current Enterprise customers are in **early evaluation
and piloting phases**, not stable production deployments. However, as they
transition to production systems, they will either:

1. **Implement formal change management processes** with defined change windows
   and release schedules, or
2. **Silently fall behind on updates** and expect support on increasingly old
   versions

**We must establish our release and support policy now** to avoid future support
burden and set proper expectations before customers reach production scale.

#### 1.3.3 Two Delivery Models

We have currently been assuming model 1, but model 2 has precident for
enterprise customers streching back well over a decade. We need to decide which
to offer--not both!

**Model 1 - Customer-Managed Installations:**

- Customer controls their own upgrade timeline and process
- **Recommended Strategy**:
  - Push for weekly adoption with high-quality releases
  - Offer quarterly LTS releases as fallback option
  - **Limit support to maximum 1 quarter behind** (following [GitLab's
    maintenance policy](https://docs.gitlab.com/policy/maintenance/))
- **Success Factor**: Consistent, stable, high-quality releases that build
  customer confidence

**Model 2 - Vendor-Managed Appliance Approach:**

- On-premises deployment but vendor-controlled update process
- Pre-agreed change processes with standard cadences
- Enables weekly standing change windows
- Reduces customer change management overhead

**Critical Success Factor:**

**The key to keeping customers current is delivering stable, high-quality
releases consistently.** If we fail to maintain release quality:

- Customers will lose confidence and resist frequent updates
- We'll face increased demands for backporting fixes to old versions
- Customer support costs will escalate significantly
- Engineering productivity will suffer from extensive backporting work

This reinforces why the proposed 1-week stagger between SaaS and Enterprise
releases is valuable—it provides a validation period to ensure Enterprise
customers receive proven, stable releases.

## 2. Envisioned Future State

### 2.1 Customer Experience

#### Enterprise Customers

- **Predictable Release Schedule**: Clear expectations for when new versions are
  available
- **Transparent Version Mapping**: Easy understanding of how Enterprise versions
  relate to SaaS releases
- **Defined Support Windows**: Clear knowledge of which versions receive
  security updates and for how long
- **Flexible Adoption Options**: Choice between staying current with frequent
  updates or using Long-Term Support (LTS) releases

#### Internal Teams

- **Automated Release Coordination**: Streamlined process for releasing
  coordinated component versions
- **Reduced Support Burden**: Clear policies limiting the number of supported
  versions
- **Improved Quality Assurance**: Staggered releases allowing SaaS validation
  before Enterprise deployment

### 2.2 Release Cadence Options

#### Option 1 - Weekly Releases with Stagger

- SaaS releases weekly (current cadence)
- Enterprise releases weekly, staggered by 1 week behind SaaS
- Provides validation period while maintaining rapid delivery

#### Option 2 - Current Cadence with Limited Support

- Enterprise releases match SaaS cadence
- Support limited to releases no more than 2 weeks old
- Encourages customers to stay current

### 2.3 Version Support Policy

#### Initial Policy (inspired by GitLab's approach)

- **Current Release**: Full bug fix and security support
- **Previous 2 Releases**: Security fixes only
- **Older Releases**: No support (customers must upgrade)

#### Future Considerations

- **Quarterly LTS Option**: Long-term support releases with security-only fixes
- **Monthly Release Cadence**: Transition to monthly Enterprise releases with
  continuous SaaS beta

## 3. Technical Solution

### 3.1 Version Numbering Strategy

#### Semantic Versioning: `MAJOR.MINOR.PATCH`

- **Component Coordination**: All related components (Runtime API, Image Loader,
  Runtimes) use consistent versioning based matching OpenHands code repo tag.
- **Containers and Charts Tagged to Match**: Containers and Charts pushed to
  package repo are tagged to match as part of the release process.

### 3.2 Release Automation

#### Automated Release Pipeline

1. **Trigger**: Based on release completion (for staggered approach) or
   concurrent with SaaS
2. **Component Coordination**: Automatically determine and tag compatible
   versions of:
   - Runtime API
   - Image Loader
   - Runtimes container
3. **Helm Chart Generation**: Generate coordinated Helm charts with proper
   version tags
4. **Release Notes**: Automated generation linking Enterprise changes to core
   OpenHands features

### 3.3 Release Artifacts

#### Standardized Release Package

- **Helm Charts**: Versioned charts for all components
- **Container Images**: Tagged with semantic versions (not just Git SHAs)
- **Release Notes**: Clear documentation of changes, security updates, and
  upgrade instructions
- **Compatibility Matrix**: Clear documentation of component version
  compatibility

#### Backporting Process

- **Automated Tooling**: Scripts to facilitate backporting critical fixes
- **Clear Criteria**: Defined standards for what qualifies for backporting
- **Limited Scope**: Restrict backports to security fixes and critical bugs only

### 3.5 Implementation Phases

#### Phase 1: Foundation

- Implement semantic versioning for all components
- Create automated release coordination pipeline
- Establish basic support policy (current + 2 releases)

#### Phase 2: Enhanced Support

- Add LTS release option (if needed based on customer feedback)
- Implement automated security update notifications
- Create customer-facing supported versions dashboard

#### Phase 3: Optimization

- Evaluate and potentially adjust release cadence based on customer adoption
  patterns
- Implement advanced backporting automation
- Consider transition to monthly release model if appropriate

## 4. Success Metrics

- **Customer Satisfaction**: Reduced support tickets related to version
  confusion
- **Engineering Efficiency**: Decreased time spent on ad-hoc backporting and
  version management
- **Security Posture**: Faster adoption of security updates by Enterprise
  customers
- **Release Quality**: Reduced critical issues in Enterprise releases through
  SaaS validation period

## 5. Next Steps

1. **Stakeholder Review**: Gather feedback from engineering, customer success,
   and sales teams
2. **Customer Input**: Survey existing Enterprise customers on preferred release
   cadence and support expectations
3. **Technical Implementation**: Begin Phase 1 implementation with automated
   versioning and release coordination
4. **Policy Communication**: Clearly communicate new support policy to existing
   and prospective customers
5. **Monitoring and Adjustment**: Track adoption patterns and adjust policy as
   needed based on real-world usage

