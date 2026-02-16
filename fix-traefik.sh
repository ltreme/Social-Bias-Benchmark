#!/bin/bash
# Script zum Beheben des Traefik-Routing-Problems auf dem Server

echo "=== Traefik Routing Fix ==="
echo ""

echo "1. Prüfe aktuelle Labels vom nginx-Container..."
docker inspect sbb-nginx-prod | grep -A 40 "Labels" || echo "Container nicht gefunden oder keine Labels"
echo ""

echo "2. Stoppe alle Container..."
docker compose -f docker-compose.production.yml down
echo ""

echo "3. Entferne verwaiste Container und Networks..."
docker system prune -f
echo ""

echo "4. Starte Container neu mit --force-recreate..."
docker compose -f docker-compose.production.yml up -d --force-recreate
echo ""

echo "5. Warte 10 Sekunden auf Startup..."
sleep 10
echo ""

echo "6. Prüfe neue Labels..."
docker inspect sbb-nginx-prod | grep -A 40 "Labels"
echo ""

echo "7. Prüfe Traefik Logs (letzte 30 Zeilen)..."
docker logs traefik --tail 30
echo ""

echo "8. Liste alle Container im proxy Netzwerk..."
docker network inspect proxy
echo ""

echo "=== Fertig! ==="
echo "Wenn du jetzt 'Creating router sbb-secure' in den Traefik-Logs siehst, hat es funktioniert!"
