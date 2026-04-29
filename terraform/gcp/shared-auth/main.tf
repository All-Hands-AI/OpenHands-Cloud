# -----------------------------------------------------------------------------
# Shared Keycloak Infrastructure for Staging Environments
# 
# Deploys a single Keycloak instance at auth.ohe-staging.platform-team.all-hands.dev
# that can be shared across multiple branch deployments, enabling:
#   - Single SAML/OIDC configuration with identity providers (Google, etc.)
#   - Consistent authentication across all staging branches
#   - Simplified identity provider management
# -----------------------------------------------------------------------------

terraform {
  required_version = ">= 1.0"
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = ">= 2.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.0"
    }
  }
}

# -----------------------------------------------------------------------------
# Namespace for shared authentication services
# -----------------------------------------------------------------------------

resource "kubernetes_namespace" "shared_auth" {
  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/name"       = "shared-auth"
      "app.kubernetes.io/managed-by" = "terraform"
      environment                    = "staging"
    }
  }
}

# -----------------------------------------------------------------------------
# Secrets - these need to be created before Keycloak deployment
# -----------------------------------------------------------------------------

resource "kubernetes_secret" "keycloak_admin" {
  metadata {
    name      = "keycloak-admin"
    namespace = kubernetes_namespace.shared_auth.metadata[0].name
  }

  data = {
    "admin-password" = var.keycloak_admin_password
  }

  type = "Opaque"
}

resource "kubernetes_secret" "postgres_password" {
  metadata {
    name      = "postgres-password"
    namespace = kubernetes_namespace.shared_auth.metadata[0].name
  }

  data = {
    username = var.postgres_username
    password = var.postgres_password
  }

  type = "Opaque"
}

# -----------------------------------------------------------------------------
# Secret for staging client credentials
# Branch deployments will reference this for their keycloak-realm secret
# -----------------------------------------------------------------------------

resource "kubernetes_secret" "staging_client" {
  metadata {
    name      = "keycloak-staging-client"
    namespace = kubernetes_namespace.shared_auth.metadata[0].name
  }

  data = {
    "realm-name"    = var.realm_name
    "client-id"     = var.client_id
    "client-secret" = var.client_secret
  }

  type = "Opaque"
}

# -----------------------------------------------------------------------------
# Shared Keycloak Helm Release
# -----------------------------------------------------------------------------

resource "helm_release" "keycloak" {
  name       = "keycloak"
  namespace  = kubernetes_namespace.shared_auth.metadata[0].name
  repository = "oci://registry-1.docker.io/bitnamicharts"
  chart      = "keycloak"
  version    = var.keycloak_chart_version

  values = [
    templatefile("${path.module}/values-keycloak.yaml", {
      hostname          = var.keycloak_hostname
      postgres_host     = var.postgres_host
      postgres_database = var.postgres_database
      tls_secret_name   = var.tls_secret_name
      ingress_class     = var.ingress_class
    })
  ]

  depends_on = [
    kubernetes_secret.keycloak_admin,
    kubernetes_secret.postgres_password
  ]
}

# -----------------------------------------------------------------------------
# ConfigMap for realm configuration template
# This can be used by branch deployments to configure their clients
# -----------------------------------------------------------------------------

resource "kubernetes_config_map" "realm_template" {
  metadata {
    name      = "keycloak-realm-template"
    namespace = kubernetes_namespace.shared_auth.metadata[0].name
  }

  data = {
    "realm-template.json" = templatefile("${path.module}/realm-template.json", {})
  }
}

# -----------------------------------------------------------------------------
# ConfigMap for realm setup script
# -----------------------------------------------------------------------------

resource "kubernetes_config_map" "realm_setup_script" {
  metadata {
    name      = "keycloak-realm-setup"
    namespace = kubernetes_namespace.shared_auth.metadata[0].name
  }

  data = {
    "setup-realm.sh" = <<-EOF
      #!/bin/sh
      set -e
      
      # Install jq if not present (alpine/curl image should have it, but just in case)
      if ! command -v jq &> /dev/null; then
        echo "Installing jq..."
        apk add --no-cache jq
      fi
      
      echo "============================================"
      echo "Keycloak Realm Setup"
      echo "============================================"
      echo "KEYCLOAK_URL: $KEYCLOAK_URL"
      echo "REALM_NAME: $REALM_NAME"
      echo "CLIENT_ID: $CLIENT_ID"
      echo "============================================"
      
      echo ""
      echo "Waiting for Keycloak to be ready..."
      RETRY_COUNT=0
      MAX_RETRIES=60
      until curl --output /dev/null --silent --head --fail "$KEYCLOAK_URL/realms/master"; do
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
          echo "ERROR: Keycloak not ready after $MAX_RETRIES attempts"
          exit 1
        fi
        echo "Keycloak not ready (attempt $RETRY_COUNT/$MAX_RETRIES), waiting 10s..."
        sleep 10
      done
      echo "Keycloak is ready!"
      
      # Get admin token
      echo ""
      echo "Getting admin access token..."
      TOKEN_RESPONSE=$(curl -s -X POST "$KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "client_id=admin-cli" \
        -d "grant_type=password" \
        -d "username=admin" \
        -d "password=$KEYCLOAK_ADMIN_PASSWORD")
      
      ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token')
      
      if [ "$ACCESS_TOKEN" = "null" ] || [ -z "$ACCESS_TOKEN" ]; then
        echo "ERROR: Failed to get admin token"
        echo "Response: $TOKEN_RESPONSE"
        exit 1
      fi
      echo "Got access token successfully"
      
      # Check if realm exists
      echo ""
      echo "Checking if realm '$REALM_NAME' exists..."
      REALM_EXISTS=$(curl -s -o /dev/null -w "%%{http_code}" \
        "$KEYCLOAK_URL/admin/realms/$REALM_NAME" \
        -H "Authorization: Bearer $ACCESS_TOKEN")
      
      if [ "$REALM_EXISTS" = "404" ]; then
        echo "Realm does not exist, creating: $REALM_NAME"
        
        # Update realm template with client secret
        jq --arg secret "$CLIENT_SECRET" \
           '.clients[0].secret = $secret' \
           /config/realm-template.json > /tmp/realm.json
        
        echo "Realm configuration:"
        jq '.realm, .clients[0].clientId' /tmp/realm.json
        
        RESPONSE=$(curl -s -w "\n%%{http_code}" -X POST "$KEYCLOAK_URL/admin/realms" \
          -H "Authorization: Bearer $ACCESS_TOKEN" \
          -H "Content-Type: application/json" \
          --data "@/tmp/realm.json")
        
        HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
        BODY=$(echo "$RESPONSE" | sed '$d')
        
        if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "204" ]; then
          echo "Realm '$REALM_NAME' created successfully!"
        else
          echo "ERROR: Failed to create realm (HTTP $HTTP_CODE)"
          echo "Response: $BODY"
          exit 1
        fi
      else
        echo "Realm '$REALM_NAME' already exists (HTTP $REALM_EXISTS)"
        echo "Checking client configuration..."
        
        # Get client UUID
        CLIENT_RESPONSE=$(curl -s "$KEYCLOAK_URL/admin/realms/$REALM_NAME/clients?clientId=$CLIENT_ID" \
          -H "Authorization: Bearer $ACCESS_TOKEN")
        
        CLIENT_UUID=$(echo "$CLIENT_RESPONSE" | jq -r '.[0].id')
        
        if [ "$CLIENT_UUID" != "null" ] && [ -n "$CLIENT_UUID" ]; then
          echo "Found client '$CLIENT_ID' with UUID: $CLIENT_UUID"
          echo "Updating client secret..."
          
          # Get current client config and update secret
          CURRENT_CLIENT=$(curl -s "$KEYCLOAK_URL/admin/realms/$REALM_NAME/clients/$CLIENT_UUID" \
            -H "Authorization: Bearer $ACCESS_TOKEN")
          
          UPDATED_CLIENT=$(echo "$CURRENT_CLIENT" | jq --arg secret "$CLIENT_SECRET" '.secret = $secret')
          
          UPDATE_RESPONSE=$(curl -s -w "\n%%{http_code}" -X PUT \
            "$KEYCLOAK_URL/admin/realms/$REALM_NAME/clients/$CLIENT_UUID" \
            -H "Authorization: Bearer $ACCESS_TOKEN" \
            -H "Content-Type: application/json" \
            --data "$UPDATED_CLIENT")
          
          HTTP_CODE=$(echo "$UPDATE_RESPONSE" | tail -n1)
          
          if [ "$HTTP_CODE" = "204" ] || [ "$HTTP_CODE" = "200" ]; then
            echo "Client secret updated successfully!"
          else
            echo "WARNING: Failed to update client (HTTP $HTTP_CODE)"
          fi
        else
          echo "WARNING: Client '$CLIENT_ID' not found in realm"
          echo "You may need to configure the client manually"
        fi
      fi
      
      echo ""
      echo "============================================"
      echo "Realm setup complete!"
      echo "============================================"
    EOF
  }
}

# -----------------------------------------------------------------------------
# Job to configure the realm after Keycloak is deployed
# -----------------------------------------------------------------------------

resource "kubernetes_job" "realm_setup" {
  metadata {
    name      = "keycloak-realm-setup"
    namespace = kubernetes_namespace.shared_auth.metadata[0].name
  }

  spec {
    ttl_seconds_after_finished = 300
    backoff_limit              = 10

    template {
      metadata {
        labels = {
          app = "keycloak-realm-setup"
        }
      }

      spec {
        restart_policy = "OnFailure"

        container {
          name  = "setup"
          image = "alpine/curl:8.5.0"  # Has both curl and jq

          command = ["/bin/sh", "/scripts/setup-realm.sh"]

          env {
            name  = "KEYCLOAK_URL"
            value = "http://keycloak:80/auth"
          }

          env {
            name  = "REALM_NAME"
            value = var.realm_name
          }

          env {
            name  = "CLIENT_ID"
            value = var.client_id
          }

          env {
            name = "CLIENT_SECRET"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.staging_client.metadata[0].name
                key  = "client-secret"
              }
            }
          }

          env {
            name = "KEYCLOAK_ADMIN_PASSWORD"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.keycloak_admin.metadata[0].name
                key  = "admin-password"
              }
            }
          }

          volume_mount {
            name       = "scripts"
            mount_path = "/scripts"
          }

          volume_mount {
            name       = "config"
            mount_path = "/config"
          }
        }

        volume {
          name = "scripts"
          config_map {
            name         = kubernetes_config_map.realm_setup_script.metadata[0].name
            default_mode = "0755"
          }
        }

        volume {
          name = "config"
          config_map {
            name = kubernetes_config_map.realm_template.metadata[0].name
          }
        }
      }
    }
  }

  depends_on = [helm_release.keycloak]
}
