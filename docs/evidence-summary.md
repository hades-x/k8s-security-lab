# Bilan de preuves — 13 octobre 2026

[Accueil](../README.md) · [Architecture](architecture.md) · [Limites](limitations.md)

Ce bilan est une **synthèse documentaire et un relevé indépendant daté**, pas un déploiement reproduit. Les preuves brutes et l'inventaire d'infrastructure restent privés. Les références E01–E12 ci-dessous identifient les sources effectivement examinées ; elles ne sont pas des liens vers des fichiers omis du package.

## Comment lire les résultats

- **Historique observé** : un rapport/objet/log d'acceptation décrit une exécution du lab d'origine.
- **Consultation indépendante** : l'opérateur a relu l'état existant le soir, sans rejouer les scénarios.
- **Non vérifié** : absence de preuve d'exécution suffisante ; ni présence du script ni PASS voisin ne comble ce manque.

Un document plus récent ne remplace que les constats portant sur le même périmètre. Les heures ci-dessous sont CEST (UTC+02:00) sauf mention UTC explicite.

## Chronologie réconciliée

| Date / heure | Observation ou résultat | Frontière de preuve | Sources |
|---|---|---|---|
| 13 octobre, 12:07 | P3 : PKI/ACME, OpenBao/ESO, sessions SSO Grafana/Argo/Forgejo, observabilité, registre et petit restore PVC acceptés | Pas de TLS LDAP, HA OpenBao ni restore hors site ; le payload restauré a le checksum d'origine | E01 |
| 13 octobre, 13:23:18 | P4 : transport Kafka TLS/SCRAM/ACL, cinq capteurs Zeek, Falco/audit et 16/17 cas de détection | `audit-anonymous` n'a pas produit de document dans ce premier run ; moteur actif Alerting ; drain lag zéro sous pause contrôlée | E02, E03 |
| 13 octobre, vers 13:45–14:35 | OOM/I/O du control-plane et remédiation D11 | Serveurs à 10 Gio et réservations ; cache unsafe introduit avec risque accepté, pas amélioration durable de performance qualifiée | E07 |
| 13 octobre, 15:30:48 | P5 : 12/12 preuves de durcissement, 57/57 attentes RBAC ; audits bornés | Baseline initiale incomplète ; pas certification CIS ; scan CVE interne encore en échec CA à ce checkpoint | E04 |
| 13 octobre, 16:06:04–16:07:36 | Pipeline Woodpecker 9, événement push natif, cinq étapes success/exit 0, durée 92 s | Mesure du pipeline seulement, hors promotion et restore ; positif/négatif d'admission et parcours métier documentés séparément | E05, E06 |
| 13 octobre, reprise du soir | D12–D14 : saturation liée aux démarrages concurrents, corruption, réparations filesystem/qcow2/Kafka/OpenSearch | Cause des arrêts hôte formulée comme probable ; six indices remis par primaires vides ont perdu leurs données historiques | E07 |
| 13 octobre, 20:26–20:28 | Le guide Phase C revoit cinq Ready et quatre applications Healthy après réparation ; Kafka encore partiellement dégradé dans ce relevé | Cette ligne explique l'ancien guide, pas le dernier état du soir | Source Phase C examinée lors de la revue |
| 13 octobre, 20:40–20:56 | Phase D : audit non authentifié corrigé, scan prod frais, création native via alias désactivée, dashboard rendu, hot-add Intel réussi mais révocation échouée | Aucun run complet 17/17 ; un seul rapport CVE ; ni finding natif actif ni hot-removal corrigé | E08 |
| 13 octobre, 20:45:49–20:57:30 | Phase E : cinq scénarios PASS, documents/alertes ou verdicts Hubble corrélés ; nettoyage consigné | Simulations bornées ; premier essai scan échoué conservé, second réussi après garde de convergence Cilium | E09 |
| 13 octobre, 21:06:31 | Phase F : quatre exercices PASS, namespaces nettoyés, nœuds schedulables | Lifecycle : cordon de 5 s et drain dry-run ; control-plane : save/list/delete snapshot, **restore non exécuté** | E10 |
| 13 octobre, 22:57:44 | Consultation indépendante : cinq Ready, API/etcd prêts, quatre applications Synced/Healthy, trois brokers Kafka Running/Ready | Aucun lag, pipeline, login, rendering, restore ou stabilité longue mesuré | E11 |
| 13 octobre, 22:58:23 | Smoke original strict-read-only : **40/40 PASS, 0 FAIL, exit 0, 3.61 s** | Pas de ressources cluster créées ; le test passe par les clients/accès privés préexistants | E12 |

Les durées des quatre exercices, dans le rapport final, sont 108 s (Debug), 136 s (Lifecycle), 42 s (Ressources) et 28 s (Control plane). Le contrôle indépendant du soir n'a **pas** rejoué ces exercices ni les cinq scénarios. Leur réussite reste historique. [Parcours pédagogique](learning-path.md).

## Ce que le contrôle indépendant a réellement ajouté

Le smoke a observé OpenSearch **green à trois nœuds**, **17/17 moniteurs enregistrés activés** et **9 406 documents `zeek-conn` dans les dix minutes précédentes**. Il a relu les PSS restricted et default-deny applicatifs, ainsi que `lab-prod-signatures` Enforce. Il a confirmé que Kafka était revenu à **trois brokers prêts**, contrairement à l'ancien guide. Il ne compte pas 17 détections déclenchées et ne mesure pas toutes les sources SOC. Le lag est explicitement exclu parce que son helper crée un Pod/ConfigMap. [E11, E12]

La lecture des conditions Certificate et deux GET HTTPS avec confiance CA ont réussi dans le smoke. Mais les échéances lues incluaient, le **14 octobre 2026**, Keycloak `09:08:59Z`, Grafana `09:25:52Z` et Argo CD `09:33:47Z`. Ces heures sont en UTC. Aucune vérification de renouvellement ultérieur n'a été réalisée ; ne pas promettre leur validité pour une démonstration future. [E11, E12]

## Corrections des affirmations devenues obsolètes

| Affirmation d'un ancien brouillon | Conclusion retenue |
|---|---|
| « Pipeline en cours, digest placeholder, signature prod absente » | P6 documente ensuite build réel, même digest déployé et admission positive/négative ; le smoke relit la policy Enforce. [E05, E06, E12] |
| « Trivy CVE interne échoue toujours en x509 » | Phase D a conservé la validation TLS, injecté la CA publique et obtenu **un** rapport prod frais à 20:52:49 : **2 CRITICAL, 10 HIGH**. Opérateur remis à zéro ; aucune couverture cluster complète. [E08] |
| « L'audit non authentifié est définitivement indétectable » | Une requête refusée 401 avec `user={}` a motivé un selector missing username + 401 ; dry-run trigger vrai. Pas nouveau PASS 17/17 avec alertes persistées. [E08] |
| « Aucun détecteur natif ne peut être créé » | Même payload accepté via alias sans point ; preuve désactivée, exécution/rollover non validés ; Alerting reste actif. [E08] |
| « Les six panels SOC n'ont jamais été rendus » | Phase D corrige les versions des panels et vérifie le rendu authentifié. La capture privée n'est pas publiée, et HTTP/SSO limité subsiste. [E08] |
| « Scénarios/exercices à compléter » | Cinq scénarios et quatre exercices ont des résultats finaux datés. Ils ne sont pas nouvellement reproduits par la revue publique. [E09, E10] |
| « Réservations kubelet partout » | L'exercice ressources observe une réservation serveur et confirme leur absence sur les agents. [E10] |
| « OpenSearch logs à zéro réplica » | D13 consigne le retour à un réplica ; cela ne récupère pas les six historiques perdus. [E07] |
| « Kafka broker 0 encore en CrashLoop » | Vrai au relevé Phase C, supersédé seulement pour l'état de 22:57–22:58 avec trois brokers prêts. [E11, E12] |

D15 conserve deux limites importantes : la CI exclut les CRITICAL sans correctif, et l'IoC interne `192.168.150.22` produit un bruit massif. Le restart Zeek consigné après l'essai de révocation ne transforme pas le hot-removal en fonctionnalité corrigée. [E07]

## Provenance documentaire sélectionnée

Les SHA-256 portent sur les **octets originaux lus**, pas sur cette synthèse. Ils servent à identifier la version privée examinée, sans rendre les sources publiques ni authentifier à eux seuls leur exactitude. L'inventaire complet de revue est conservé hors du package.

| Référence | Source examinée | SHA-256 |
|---|---|---|
| E01 | P3 infrastructure acceptance | `336e22596c275c2ca34b8d61ec914ffd118b063f31bc1da013541b00d3f8e9b2` |
| E02 | P4 SOC acceptance | `fa3f0ffede1db267bb23513bba3121d74d747f97254c4cf184395489b4d316d5` |
| E03 | P4 per-rule detection results | `60254f2cfe8dfcf549b129609dd1f9d7400d44bec8aebd805326ce5e8f86710f` |
| E04 | P5 hardening report | `0ac779f68fd9fc1160dba9c80d0a2fb43e13f75317a4a00abf5fe766ae1502a6` |
| E05 | P6 delivery acceptance narrative | `43989139169ee559a4660596b1cf9e33efc20bcf5f567b6d75fce0c86fb48b91` |
| E06 | Pipeline 9 API record | `2d4d66cee63f040e71eaf90bde610e924922ef2aaca3c7964e607249e16580fd` |
| E07 | Decision log D11–D15 | `ac4313510a1a240533ff5d2c2b2878daa2144655f6f794782ec776288aeb136e` |
| E08 | Phase D bounded fixes report | `e8e0e1bab6c604e1ab19bd6652f75503dbf60fcb9445086cacffd0855295f7f9` |
| E09 | Phase E scenario results | `a17f98cb95e5f9e0d20f78b887e046008ff3312f67f027300207b6382e79a33b` |
| E10 | Phase F verified report | `6d56cb39964a3b2cdffddb376d02f589d488d55b9d228185d73a164c3796f25f` |
| E11 | Independent operator readback | `0daea4e80ee122bac2ee35f1c24f532bb9e1dec974420d0bc2e294288e640413` |
| E12 | Independent strict-read-only smoke log | `8850f3531a947408be534825d795413f89ee068ad048f2af665fff792095dedc` |

## Non démontré par ce dossier

Recréation clean-clone, restore complet etcd, PRA hors hôte, cold-start portable sain, pipeline rejoué pendant le contrôle indépendant, nouvelle validation exhaustive des détections, campagne de charge et stabilité prolongée restent non vérifiés. Aucun run CI public GitHub n'est présenté. Les [limites](limitations.md) font partie des résultats du projet, pas d'un travail effacé par les PASS.
