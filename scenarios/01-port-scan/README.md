> **Automatisation désactivée dans cette version publique** : les runners/cleanup sont conservés comme référence historique, mais refusent toute exécution, même avec `LAB_ALLOW_RUNTIME=yes`. Les fiches et manifests restent des supports de lecture/manipulation manuelle sur un lab jetable autorisé. Adaptation UID/run, erreurs API et ownership exact des snapshots requise avant réactivation; voir `tools/DEPENDENCIES.md` depuis la racine.

> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# 01 — Reconnaissance interne bornée

## Ce que ça démontre
Un pod ne contacte que les ports 2000–2019 d’un serveur factice sur un autre nœud. Aucun balayage de CIDR, aucun exploit.

- **ATT&CK :** T1046. Émulation défensive, pas preuve d’exploitation réelle.
- **Source :** Zeek conn/notice → Vector → Kafka → OpenSearch.
- **Règle / résultat attendu :** conn-scan (cardinalité ≥12 ports) et notice-scan (Lab::Port_Scan).
- **Réponse :** Marquage quarantine=true et CiliumNetworkPolicy quarantine ; HTTP autorisé avant, puis timeout et Hubble DROPPED après.
- **Preuves :** `evidence/scenarios/01.log` et `evidence/scenarios/01/` : conn-scan-alerts.json ; notice-scan-alerts.json. Les manifests réellement appliqués et les GET de lecture retour sont conservés dans `manifests/` et `readback/`.

## Rejouer (lab controller)
```bash
cd /data/k8s-lab
export LAB_TRIGGER=1
scenarios/01-port-scan/generate.sh
scenarios/01-port-scan/detect.sh
scenarios/01-port-scan/respond.sh
scenarios/01-port-scan/verify.sh
scenarios/01-port-scan/cleanup.sh
```
Pour le nettoyage garanti même sur erreur, utiliser `LAB_TRIGGER=1 scenarios/run-all.sh 01`.

## Critères de preuve et limites
`generate.sh` exécute `make -s status-quick` et refuse tout événement si un nœud est NotReady, si MemAvailable <4 GiB ou si les pods en récupération ne sont pas Ready. Il crée exclusivement ses namespaces `scen-e01-*` ; un namespace déjà présent n’est jamais adopté. Images réutilisées du lab, épinglées par digest ; pods non-root, capacités supprimées, budgets CPU/RAM, durée de vie bornée ; aucun téléchargement de paquet dans les pods.

`detect.sh` retourne non-zéro sans preuve fraîche et corrélée au client de cette exécution. Pour OpenSearch, une copie désactivée du monitor existant est bornée par IP/marqueur + début de run, exécutée une fois avec `dryrun=false`, et doit produire une alerte ACTIVE persistée relue via l’API. Les règles P4 restent inchangées et aucune notification externe n’est configurée. Les copies désactivées et leurs alertes restent pour l’entretien ; pas de scheduler supplémentaire actif. Pour Hubble, IP source/destination et verdict doivent correspondre au flux testé.

Les scripts de déclenchement existants imposent `soc-detection` ou mutent les capteurs pour le rejeu ; ils ne sont donc pas appelés hors périmètre. On réutilise leurs règles, marqueur shell, garde LAB_TRIGGER et template de quarantaine. Toutes les cibles sont les pods factices du lab ; les domaines sont sous `.lab.test`. `verify.sh` teste le dataplane, pas seulement les labels. Le résultat réellement mesuré est publié dans `../README.md` et `evidence/scenarios/results.json`. Un script livré ou un monitor importé sans preuve n’est pas un PASS.
