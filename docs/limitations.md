# Limites, incidents et risques conservés

[Accueil](../README.md) · [Architecture](architecture.md) · [Chronologie](evidence-summary.md)

Les réussites historiques ne ferment pas les risques ci-dessous. Cette page distingue défaut de conception de lab, incident observé et vérification manquante.

## Disponibilité et durabilité

- **Un seul domaine de panne physique.** Control-plane, Kafka, OpenSearch, volumes et backup partagent un hyperviseur et son stockage. Réplication applicative et Longhorn entre invités ne créent pas une indépendance matérielle.
- **Cache disque unsafe.** Le choix historique réduit la pression fsync mais sacrifie la durabilité des écritures invitées lors d'un crash hôte. Son retrait du lab d'origine n'est pas démontré. Le provisioner du package public utilise `cache=none` pour de nouveaux disques ; ce changement de source n'a pas été validé par un nouveau déploiement. L'arrêt propre est une procédure de réduction du risque, pas une garantie crash-safe ni une recommandation production.
- **Pertes réelles.** Après arrêts brutaux, filesystem invité, métadonnées qcow2, checkpoints Kafka et shards OpenSearch ont nécessité des réparations. Six indices de logs ont été réalloués par primaires vides : le retour green n'a pas restauré leur histoire. Un replay intégral depuis Kafka n'est pas prouvé.
- **Reprise non qualifiée.** Un ancien démarrage de 1 285 secondes s'est terminé avec seulement quatre nœuds Ready. Une réparation et des contrôles ultérieurs ont retrouvé cinq Ready ; cela ne mesure ni un cold-start propre portable ni une stabilité longue.

## Ressources et livraison des événements

Le budget initial de 44 Gio était insuffisant dans les conditions observées. Les serveurs sont passés à 10 Gio, avec réservations kubelet et filtrage de l'audit système. Le module ressources a néanmoins confirmé l'absence de réservations sur les agents. Les limites de conteneurs peuvent dépasser la RAM disponible cumulée ; ce n'est pas une capacité garantie.

Le SOC est at-least-once, avec doublons possibles. Des événements d'audit initiaux ont été rejetés avant correction des mappings et n'ont pas été backfillés. Le drain à lag zéro a quiescé les producteurs ; des événements Falco pouvaient être manqués pendant la pause du receiver. Ni débit soutenu, ni p95/p99, ni taux de perte/doublons, ni RPO/RTO n'ont été qualifiés. Le smoke indépendant ne mesure pas le lag Kafka.

## Détection et renseignement

- Les **16/17** cas synthétiques du premier run SOC ne sont pas un pourcentage de couverture des attaques réelles. Le selector d'une tentative API non authentifiée a ensuite été corrigé et déclenché en dry-run ; le pack complet n'a pas été rejoué pour établir 17/17 alertes persistées.
- Alerting est le moteur actif. Security Analytics a échoué sur des noms d'index datés avec points ; une création via alias sans point a réussi, mais le détecteur est resté désactivé. Exécution native et gestion du rollover restent non validées.
- L'ajout Intel à chaud a été observé. **La révocation immédiate à chaud a échoué** : `Input::REREAD` réinsère sans purger le datastore. Un restart contrôlé des capteurs a ensuite été consigné, pas une correction de ce comportement.
- Un IoC synthétique a réutilisé `192.168.150.22`, IP d'un nœud. Il a généré un bruit massif ; l'adresse est une mauvaise fixture de renseignement. Préférer une valeur dédiée comme `ioc.evil-c2.lab.test`, vérifier provenance/contexte et allowlists, ne pas qualifier toute correspondance de compromission.
- Il n'y a pas de notification externe ni de boucle analyste → MISP automatique démontrée. Les scénarios sont défensifs et bornés ; le cas latéral ne prouve pas une exploitation distante.

## Contrôles et confiance

| Sujet | Limite retenue |
|---|---|
| Réseau | Default-deny applicatif, pas universel SOC/infra ; passerelle de l'hôte joignable |
| Privilèges | Capteurs, stockage et audit administrateur nécessitent des exceptions explicites |
| RBAC | 57 attentes testées ; refus Secret GET ne ferme pas les montages de Secret ou choix de SA via un workload |
| Ingress SOC | Dashboards/MISP et certaines interfaces utilisent HTTP de lab ; ne pas exposer au public |
| Identité | Keycloak mode dev mono-instance, LDAP interne en clair ; SSO applicatif ≠ OIDC Kubernetes API |
| Secrets | OpenBao mono-nœud, unseal manuel Shamir 1/1, transport interne limité ; pas HA/auto-unseal |
| PKI | Racine « offline » conservée sur l'hôte connecté, pas custody physique/HSM ; fallback CA expose une copie de clé intermédiaire |
| TLS | Plusieurs certificats proches de l'expiration au relevé final ; Ready ne garantit pas le renouvellement |

Les anciens certificats et clés publiques de signature ne sont pas des trust roots portables à reprendre aveuglément. Générer une nouvelle PKI et un nouveau signer dans un environnement recréé, puis injecter et vérifier les références publiques correspondantes.

## Supply chain et application

Le gate Trivy utilise `--severity CRITICAL --ignore-unfixed --exit-code 1` : les CRITICAL non corrigibles et les HIGH ne bloquent pas ce gate. Après correction de la confiance CA, **un** rapport prod frais a trouvé **2 CRITICAL et 10 HIGH**. Ce n'est ni une image sans vulnérabilités ni une couverture complète du cluster. L'opérateur a été arrêté après le scan borné.

Le signer est une clé de lab ; la compatibilité cosign/Kyverno utilise des formats hérités et n'établit pas de transparence publique/keyless. SBOM et attestation de provenance vérifiés ne sont pas revendiqués. Les promotions historiques sont des commits directs, sans approbation PR obligatoire.

Les bases PostgreSQL sont mono-instance, Valkey est un cache et l'API n'a pas d'auth HTTP. Sans outbox, le commit SQL et la publication Kafka ne sont pas atomiques. La signature de l'image n'améliore pas cette sémantique métier.

## Reproduction, audit et publication

La reconstruction à zéro sur un clone vierge et la restauration complète etcd sont **non vérifiées**. Le restore Velero porte sur une petite fixture locale. Sauvegarde hors hôte et contrôle applicatif/PVC après restore etcd restent à produire.

Les audits n'établissent aucune certification CIS : baseline initiale incomplète, périmètre borné, couverture dégradée et erreurs de mesure de certains scanners. Les comparaisons de manifests reconstruits ne sont pas un avant/après causal de l'ensemble du cluster.

Aucun cloud déployé, benchmark soutenu, HPA/KEDA, Chaos Mesh ou campagne de charge n'est prouvé. Aucun run GitHub Actions public n'est disponible au moment de cette revue. Le propriétaire a choisi de ne pas ajouter de licence au projet pour le moment ; les notices tierces restent distinctes. La revue finale de confidentialité et de provenance reste une condition de publication.
