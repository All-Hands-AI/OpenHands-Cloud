PROJECTDIR := $(shell pwd)

CHARTDIR    := $(PROJECTDIR)/charts
CHARTS      := $(shell find $(CHARTDIR) -mindepth 1 -maxdepth 1 -type d -exec basename {} \;)

MANIFESTDIR := $(PROJECTDIR)/replicated
MANIFESTS   := $(shell find $(MANIFESTDIR) -name '*.yaml' -o -name '*.yml')
CHART_YAMLS := $(shell find $(CHARTDIR) -name 'Chart.yaml')

VERSION     ?= $(shell yq .version $(CHARTDIR)/openhands/Chart.yaml)
REPLICATED_APP ?= openhands
CHANNEL     := $(shell git branch --show-current)
ifeq ($(CHANNEL), main)
	CHANNEL=Unstable
endif

BUILDDIR      := $(PROJECTDIR)/build
RELEASE_FILES :=

define make-manifest-target
$(BUILDDIR)/$(notdir $1): $1 $(CHART_YAMLS) | $$(BUILDDIR)
	cp $1 $$(BUILDDIR)/$$(notdir $1)
	@CHART_NAME=$$$$(yq '.spec.chart.name // ""' $$(BUILDDIR)/$$(notdir $1)); \
	if [ -n "$$$$CHART_NAME" ] && [ -f $(CHARTDIR)/$$$$CHART_NAME/Chart.yaml ]; then \
		CHART_VER=$$$$(yq .version $(CHARTDIR)/$$$$CHART_NAME/Chart.yaml); \
		yq -i ".spec.chart.chartVersion = \"$$$$CHART_VER\"" $$(BUILDDIR)/$$(notdir $1); \
		echo "Updated $$(notdir $1) chartVersion to $$$$CHART_VER"; \
	fi
RELEASE_FILES := $(RELEASE_FILES) $(BUILDDIR)/$(notdir $1)
manifests:: $(BUILDDIR)/$(notdir $1)
endef
$(foreach element,$(MANIFESTS),$(eval $(call make-manifest-target,$(element))))

define make-chart-target
$(eval VER := $(shell yq .version $(CHARTDIR)/$1/Chart.yaml))
$(BUILDDIR)/$1-$(VER).tgz : $(CHARTDIR)/$1 $(shell find $(CHARTDIR)/$1 -name '*.yaml' -o -name '*.yml' -o -name "*.tpl" -o -name "NOTES.txt" -o -name "values.schema.json") | $$(BUILDDIR)
	helm package -u $(CHARTDIR)/$1 -d $(BUILDDIR)/
RELEASE_FILES := $(RELEASE_FILES) $(BUILDDIR)/$1-$(VER).tgz
charts:: $(BUILDDIR)/$1-$(VER).tgz
endef
$(foreach element,$(CHARTS),$(eval $(call make-chart-target,$(element))))

$(BUILDDIR):
	mkdir -p $(BUILDDIR)

.PHONY: clean
clean:
	rm -rf $(BUILDDIR)

.PHONY: lint
lint: clean $(RELEASE_FILES)
	replicated release lint --yaml-dir $(BUILDDIR)

.PHONY: release
release: clean $(RELEASE_FILES) lint
	replicated release create \
	 	--app $(REPLICATED_APP) \
		--version $(VERSION) \
		--yaml-dir $(BUILDDIR) \
		--ensure-channel \
		--promote $(CHANNEL)
