# Solutions pour résoudre le conflit Git sur le serveur

## Problème actuel
```
error: Your local changes to the following files would be overwritten by merge:
        config.yaml
Please commit your changes or stash them before you merge.
```

## Solution 1 : Sauvegarder et mettre à jour (Recommandé)

```bash
cd /etc/proxyox

# Sauvegarder votre config
cp config.yaml config.yaml.backup

# Sauvegarder .env si présent
cp .env .env.backup 2>/dev/null || true

# Stash les modifications
git stash

# Pull les mises à jour
git pull origin main

# Restaurer votre config
cp config.yaml.backup config.yaml
cp .env.backup .env 2>/dev/null || true

# Mettre à jour les dépendances
pip3 install -r requirements.txt --quiet --upgrade

# Redémarrer
systemctl restart proxyox
```

## Solution 2 : Utiliser le script de mise à jour

```bash
cd /etc/proxyox
wget -qO update-with-config-backup.sh https://raw.githubusercontent.com/Zevoxsh/ProxyOX/main/update-with-config-backup.sh
chmod +x update-with-config-backup.sh
sudo ./update-with-config-backup.sh
```

## Solution 3 : Reset complet (⚠️ Perd la config)

```bash
cd /etc/proxyox
git reset --hard origin/main
git pull origin main
# Puis reconfigurez config.yaml manuellement
```

## Vérification après mise à jour

```bash
# Vérifier le statut
systemctl status proxyox

# Voir les logs
journalctl -u proxyox -f

# Vérifier que le mode flexible est actif
grep -A 10 "frontends:" /etc/proxyox/config.yaml | grep flexible
```

## Configuration actuelle recommandée

Votre `config.yaml` devrait contenir :

```yaml
frontends:
  - name: tcp-fe
    bind: 0.0.0.0:443
    mode: tcp
    default_backend: tcp-server
    flexible: true  # ← Mode flexible activé
```

Ceci permet au proxy de :
- Accepter HTTPS de Cloudflare
- Transmettre en HTTP au backend
- Résoudre l'erreur "plain HTTP request was sent to HTTPS port"
