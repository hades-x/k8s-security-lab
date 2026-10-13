# Démo de cinq minutes, sans mutation du cluster

[Accueil](../README.fr.md) · [Architecture](architecture.md) · [Preuves historiques](evidence-summary.md)

## Mode par défaut : visite du dépôt

Cette visite fonctionne sans cluster. Elle ne prétend pas afficher des services actuels.

| Temps | Support | Point à expliquer |
|---|---|---|
| 0:00–1:00 | [Architecture](architecture.md), vue globale | Trois serveurs etcd, deux agents, mais un seul domaine de panne physique |
| 1:00–2:00 | Chaîne SOC et [code des composants](../soc/README.md) | Réseau, runtime et audit répondent à des questions différentes ; Kafka découple collecte et indexation |
| 2:00–3:00 | [Hardening](../hardening/README.md) | Admission, RBAC et réseau se complètent ; l'accès indirect aux Secrets reste une limite |
| 3:00–4:00 | [DevSecOps](../devsecops/README.md) et application | Digest signé, scan des CRITICAL corrigibles, promotion Git ; pas d'innocuité garantie |
| 4:00–5:00 | [Bilan](evidence-summary.md) et [limites](limitations.md) | Contrôle indépendant 40/40 ; perte de données passée ; reconstruction propre et restore etcd non démontrés |

Formulation courte : « Ce projet relie les contrôles à des observations datées. Je peux expliquer les résultats des tests du lab et leurs limites ; je ne présente pas ce dossier comme une plateforme de production ou une reconstruction déjà réussie. »

## Variante : consultation d'un lab existant

Prérequis : l'opérateur a autorisé la cible, configuré `kubectl`, vérifié le routage et préparé les sessions privées. Ces commandes sont proposées ; ce document ne les présente pas comme une nouvelle exécution. Elles ne nécessitent pas de démarrer un test de phase.

```sh
# Vérifier le contexte avant toute consultation.
kubectl config current-context
kubectl get nodes -o wide
kubectl get --raw '/readyz?verbose'
kubectl -n argocd get applications
kubectl -n kafka get kafka soc
kubectl -n kafka get pods -l strimzi.io/broker-role=true
kubectl get clusterpolicies
kubectl -n prod get networkpolicies
kubectl get certificates -A
```

Le relevé de readiness etcd ne remplace pas un MemberList, un test de bascule ou une restauration. Les applications doivent être **Synced et Healthy**. Une policy Ready montre un contrôle configuré ; elle ne rejoue pas un refus d'admission.

Si une interface est disponible, ouvrir les sessions avant le partage d'écran. Pour le SOC, utiliser **SOC overview**, puis **Alerting → Alerts**. Choisir une alerte avec heure, règle et contexte ; ne pas promettre que les anciens IDs existent encore. Le détecteur natif Security Analytics de preuve est désactivé : ne pas le montrer comme chaîne active.

### Faire parler une observation

| Observation | Conclusion permise | Conclusion interdite |
|---|---|---|
| Nœuds Ready et API readyz | Disponibilité de ces ressources au moment lu | Résilience à une panne de l'hôte |
| Moniteurs enabled | Contrôles enregistrés et activés | Toutes les règles viennent de déclencher correctement |
| Document récent | Au moins ce signal a été indexé récemment | Zéro perte, latence bornée ou source complète |
| Image par digest / signature policy Enforce | État d'image et admission configurée | Nouveau build ou rejet non signé exécuté pendant la visite |
| Certificate Ready | Émission déclarée réussie | Validité future et renouvellement acquis |
| Backup/Restore Completed | Objets du drill présents | Données restaurées correctes sans lecture/checksum |

Au relevé du 13 octobre 2026 au soir, plusieurs certificats expiraient le 14 octobre. Vérifier leur échéance effective avant une session ultérieure ; ne pas afficher un ancien PASS TLS comme preuve de validité actuelle. Importer seulement la CA publique générée pour le lab et utiliser une confiance explicite. Ne pas contourner la validation TLS avec `-k` pour un login.

## Commandes à garder hors de la visite

- Installateurs, `phase-*.sh` complets, triggers SOC et runners de scénarios/exercices.
- Démarrage/arrêt de VM, reboot, cordon, drain, snapshot ou restauration.
- Réparations qcow2, Kafka ou OpenSearch, notamment allocation de primaires vides.
- Publication Forgejo, pipeline CI, POST de commande métier ou test d'admission mutateur.
- Affichage des mots de passe, tokens, matériel d'unseal, kubeconfig brut ou données de Secrets.

L'ancien `make status` mesurait le lag via création d'un Pod/ConfigMap : son nom et son aide ne le rendaient pas strictement read-only. Un helper qui porte une option `--read-only` doit être relu avec ses dépendances. La visite utilise des GET explicites plutôt qu'un alias ambigu.

## Si le direct échoue

Conserver la sortie et sa date, puis revenir à la visite du dépôt. Dire quel contrôle est indisponible ; ne pas remplacer sa sortie par un exemple fabriqué ou une capture historique présentée comme actuelle. Un lab dégradé permet encore d'expliquer l'architecture, la méthode et les limites, sans lancer de réparation pendant la présentation.
