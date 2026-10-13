> **Automatisation désactivée dans cette version publique** : les runners/cleanup sont conservés comme référence historique, mais refusent toute exécution, même avec `LAB_ALLOW_RUNTIME=yes`. Les fiches et manifests restent des supports de lecture/manipulation manuelle sur un lab jetable autorisé. Adaptation UID/run, erreurs API et ownership exact des snapshots requise avant réactivation; voir `tools/DEPENDENCIES.md` depuis la racine.

> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# Phase E — cinq validations défensives reproductibles

Simulations personnelles sur K8S-LAB : trafic synthétique uniquement, cibles pod du lab, domaines `.lab.test`, aucun exploit ni cible externe. Priorité absolue à la stabilité.

| Scénario | ATT&CK | Détection requise | Réponse vérifiée | Résultat |
|---|---|---|---|---|
| 01-port-scan | T1046 | conn-scan **et** notice-scan ; documents frais et alertes ACTIVE | Quarantaine Cilium ; HTTP timeout et Hubble DROPPED | **PASS** — `evidence/scenarios/01.log` |
| 02-dns-intel | T1071.004 | dns-c2 **et** intel-hit ; MISP/export identifié | Quarantaine ; HTTP/DNS arrêtés et Hubble DROPPED | **PASS** — `evidence/scenarios/02.log` |
| 03-lateral-netpol | T1021, analogie sans exploitation | Hubble DROPPED puis FORWARDED, mêmes IP/port | Retrait de l’allow + quarantaine ; nouveau DROPPED | **PASS** — `evidence/scenarios/03.log` |
| 04-shell-admission | T1609 | Falco shell → Kafka → OpenSearch alerte ; admission privilégiée refusée | Quarantaine réseau + nouveau refus PSS/Kyverno | **PASS** — `evidence/scenarios/04.log` |
| 05-forbidden-secret | T1552.007 | Vrai jeton SA : 403 ; audit indexé ; alerte Forbidden secret access | Révocation de RoleBinding + quarantaine ; can-i=no et DROPPED | **PASS** — `evidence/scenarios/05.log` |

## Exécution
```bash
cd /data/k8s-lab
source infra/k3s/env.sh
LAB_TRIGGER=1 scenarios/run-all.sh             # séquentiel, cleanup même sur erreur
LAB_TRIGGER=1 scenarios/run-all.sh 03          # scénario unique
# Deux tentatives maximum, option explicite :
LAB_TRIGGER=1 SCENARIO_ATTEMPTS=2 scenarios/run-all.sh 02
python3 scenarios/test_unit.py                 # tests offline, aucun événement cluster
python3 scenarios/test_report.py               # un drapeau seul ne vaut jamais PASS
python3 scenarios/report.py                    # certifie les preuves et actualise la table
```

Chaque dossier contient `generate.sh`, `detect.sh`, `respond.sh`, `verify.sh`, `cleanup.sh`, un README français et un exemple de manifest restreint. Le moteur commun est `runner.py` ; les manifests exacts et leurs GET de lecture retour sont conservés dans `evidence/scenarios/<NN>/`. Le résultat réel vient de `evidence/scenarios/results.json`, avec logs `evidence/scenarios/<NN>.log`.

## Garde-fous et méthode de preuve
- `make -s status-quick` avant **chaque** scénario. Aucun événement si un nœud est NotReady, MemAvailable <4 GiB ou si Kafka/OpenSearch/step-ca/garage/loki/prod-db sont encore en récupération.
- Un namespace déjà existant n’est jamais adopté. Les UID + label de run sont vérifiés avant mutations/nettoyage. Toutes les ressources de test sont dans les namespaces créés `scen-e<NN>-source/target`, tous les pods sont supprimés à la fin ; manifests et preuves restent. Aucun commit, VM ou hôte modifié.
- Pods factices non-root, restricted v1.36, capabilities ALL supprimées, token opt-out sauf le client SA nommé de 05 ; CPU/RAM bornés, deadline 1200 s. Image Python déjà épinglée dans le lab ; aucune installation de paquet.
- Les triggers P4 ne sont pas appelés car ils imposent des écritures hors `scen-*`. Leurs règles/queries, la logique de marqueur shell et `hardening/netpol/isolate-template.yaml` sont réutilisés. Aucun capteur global redémarré.
- Une copie de monitor désactivée, sans action externe, corrélée au run (IP et début, ou container+marqueur, ou SA+namespace), est exécutée une seule fois. PASS exige documents frais, déclenchement vrai et alerte ACTIVE persistée relue par l’API ; les 17 monitors P4 restent inchangés. Copies désactivées et alertes conservées pour l’entretien.
- La propagation du label de Pod vers l’identité de sécurité Cilium a pris 16–18 s lors du premier essai de 01. `verify.sh` attend désormais (maximum 90 s) `CiliumEndpoint.status.identity.labels` contenant `k8s:quarantine=true` et état ready, puis prouve le dataplane ; un label API seul ne vaut pas confinement. Le premier FAIL est conservé, le second essai est PASS.
- Hubble est interrogé via un port-forward loopback temporaire vers le relay. Les verdicts doivent correspondre aux IP source/destination testées ; aucun simple timeout n’est présenté comme preuve suffisante de policy.

## Points d’attention
Le filtre Vector D11 conserve explicitement `r == "secrets"`, y compris les GET `system:serviceaccount:*` refusés. Il n’est pas modifié préventivement. La nouvelle règle Sigma `soc/detection/rules/audit-forbidden-secret.yaml` cible seulement `scen-*` et les 403 ; son monitor de run est géré ici (pas ajouté aux 17 monitors P4 dont les installateurs imposent encore ce nombre). La Sigma est validée et convertie par pySigma, mais **son import natif Security Analytics n’est pas revendiqué** : `install-security-analytics.py` contient encore une assertion de 17 règles alors que le dossier en contient désormais 18. Adapter ce comptage avant un ré-import P4 ; les six preuves finales Phase E utilisent l’Alerting fallback réellement testé.

Le refresh MISP est d’abord observé read-only. Si son API n’est pas disponible, 02 utilise le dernier export `zeek-intel`, en conservant son resourceVersion et le TSV. Cela **ne prouve pas** un refresh fonctionnel ; le TTL Zeek de 20 min peut empêcher un hit frais et doit produire FAIL, jamais un événement Intel inventé. Aucun secret de credential n’est copié dans les preuves.

La quarantaine coupe le réseau du pod, **pas** le droit `kubectl exec` d’un administrateur. 03 démontre segmentation/allowlisting, pas authentification distante ou exploitation T1021. 05 utilise un nom de Secret factice non créé : le 403 prouve l’autorisation, pas l’existence ni le contenu du Secret. Les tentatives d’admission privilégiée sont faites en dry-run serveur et doivent être refusées avant création.
