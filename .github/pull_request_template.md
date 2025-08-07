## Description

<!-- Provide a brief description of the changes in this PR -->

## Type of Change

<!-- Mark the relevant option with an "x" -->

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Chart configuration change

## Helm Chart Checklist

<!-- REQUIRED: Complete this checklist if you have modified any Helm charts -->

- [ ] I have updated the `version` field in `Chart.yaml` for each modified chart
- [ ] I have tested the chart upgrade path from the previous version
- [ ] I have verified backwards compatibility with existing values.yaml configurations
- [ ] I have updated the chart's README.md if there are any breaking changes or new required values
- [ ] I have tested the chart with both minimal and full values configurations

## Testing

<!-- Describe the tests you ran to verify your changes -->

- [ ] I have tested the Helm chart deployment with `helm install`
- [ ] I have tested the Helm chart upgrade with `helm upgrade`
- [ ] I have verified the deployment with `kubectl get pods` and checked logs
- [ ] I have tested with custom values files if applicable

## Additional Notes

<!-- Any additional information that reviewers should know -->
