---
tags: [dop-c02, aws, devops, sdlc]
domaine: "1 — SDLC Automation (22% de l'examen)"
---

# DOP-C02 — Domaine 1 : SDLC Automation

> Poids : **22%** (le plus gros domaine de l'examen).
> Angle des questions : « quelle est la solution la **plus automatisée / la moins d'ops overhead** qui respecte la contrainte X ? »

---

## 1. CodeCommit

- Git managé, chiffré au repos (KMS) et en transit. Auth : **HTTPS Git credentials IAM**, **SSH keys**, ou **git-remote-codecommit** (recommandé avec SSO/rôles).
- **Cross-account** : rôle IAM dans le compte du repo + `sts:AssumeRole` depuis l'autre compte.
- **Branch protection** : pas de fonctionnalité native → **IAM policy** avec condition `codecommit:References` + `Deny` sur `GitPush`/`DeleteBranch` pour `refs/heads/main`. ⚠️ Piège classique d'examen.
- Notifications/triggers : **EventBridge** (recommandé, plus riche) ou **SNS/Lambda triggers** (legacy). Approval rule templates pour forcer N approbateurs sur les PR.

## 2. CodeBuild

- `buildspec.yml` à la **racine** du repo (ou spécifié inline dans le projet).
- Phases : `install` → `pre_build` → `build` → `post_build`. Puis `artifacts`, `cache`, `reports`.
- **Secrets** : jamais en clair dans les env vars → `parameter-store:` (SSM) ou `secrets-manager:` dans la section `env`.
- **VPC config** : nécessaire pour accéder à RDS/ElastiCache/ressources privées. Requiert subnets **privés + NAT** (ou VPC endpoints) pour joindre S3/CloudWatch/ECR.
- **Cache** : `S3` (partagé entre builds) ou `LOCAL` (`DOCKER_LAYER`, `SOURCE`, `CUSTOM` — sur le même host, plus rapide mais pas garanti).
- **Reports** : `reports:` avec `file-format` (JUNITXML, CUCUMBERJSON…) → rapports de tests visibles dans la console.
- **Batch builds** : builds parallèles (matrice multi-env / multi-plateforme) dans une seule action de pipeline.
- Docker : nécessite le mode **privileged** pour builder des images.
- Logs → CloudWatch Logs et/ou S3.

## 3. CodeArtifact & CodeGuru

- **CodeArtifact** : dépôt de packages (npm, pip, Maven, NuGet). **Upstream repositories** → proxy vers npmjs/PyPI publics avec cache. Domain = clé KMS partagée + dédup du stockage. Résout « comment centraliser et contrôler les dépendances tierces ».
- **CodeGuru Reviewer** : analyse statique/ML du code sur les PR (bugs, fuites de secrets, ressources non fermées).
- **CodeGuru Profiler** : profiling **runtime** (CPU/heap) → identifie les lignes coûteuses en prod.
- Mnémo : *Reviewer = avant le merge, Profiler = en production.*

## 4. CodeDeploy

### Plateformes et `appspec`

| Plateforme | Fichier | Contenu clé |
|---|---|---|
| EC2 / On-premises | `appspec.yml` | `files` (copie) + `hooks` (scripts) |
| Lambda | `appspec.yml/json` | version alias `CurrentVersion` → `TargetVersion` |
| ECS | `appspec.yml/json` | task definition, container name/port |

Requiert l'**agent CodeDeploy** sur EC2/on-prem uniquement (pas pour Lambda/ECS).

### Hooks — ordre à connaître par cœur

**EC2/On-prem (in-place)** :
`ApplicationStop` → `DownloadBundle` → `BeforeInstall` → `Install` → `AfterInstall` → `ApplicationStart` → `ValidateService`

Avec load balancer, s'ajoutent : `BeforeBlockTraffic` / `BlockTraffic` / `AfterBlockTraffic` (au début) et `BeforeAllowTraffic` / `AllowTraffic` / `AfterAllowTraffic` (à la fin).
⚠️ `DownloadBundle`, `Install`, `BlockTraffic`, `AllowTraffic` ne sont **pas scriptables**.

**Lambda** (seulement 2 hooks scriptables) :
`BeforeAllowTraffic` → `AllowTraffic` → `AfterAllowTraffic`

**ECS** :
`BeforeInstall` → `Install` → `AfterInstall` → `AllowTestTraffic` → `AfterAllowTestTraffic` → `BeforeAllowTraffic` → `AllowTraffic` → `AfterAllowTraffic`

→ Les hooks sont des **fonctions Lambda** qui doivent appeler `PutLifecycleEventHookExecutionStatus` (Succeeded/Failed). C'est là qu'on place les **tests de validation** avant de basculer le trafic.

### Deployment configurations

- EC2 : `CodeDeployDefault.OneAtATime` / `HalfAtATime` / `AllAtOnce`, ou custom (min healthy hosts en % ou nombre).
- Lambda & ECS : familles `Canary…`, `Linear…`, `AllAtOnce` (liste exacte dans le mémo en bas — ECS a moins de variantes que Lambda).
  - **Canary** = 2 paliers (X% puis 100%). **Linear** = incréments réguliers.

### Rollback

- **Automatic rollback** : sur échec de déploiement **ou** sur alarme CloudWatch (à activer explicitement).
- Le rollback = **nouveau déploiement** de la dernière révision connue bonne (pas un « retour arrière »).
- Blue/Green EC2 : nouvel ASG créé, `terminationWaitTimeInMinutes` avant de tuer l'ancien → fenêtre de rollback instantané.

### Dépannage CodeDeploy (tombe souvent)

- Déploiement bloqué / instances en échec → **agent CodeDeploy** absent ou arrêté, ou **instance profile** sans accès au bucket S3 des révisions.
- `ApplicationStop` échoue en boucle → c'est le script de l'**ancienne** révision qui plante → `--ignore-application-stop-failures`.
- `appspec.yml` doit être à la **racine** du bundle.
- Logs : `/var/log/aws/codedeploy-agent/` + logs de déploiement sous `/opt/codedeploy-agent/deployment-root/`.
- Script trop long → timeout du hook (paramètre `timeout` dans l'appspec, max 3600 s).

## 5. CodePipeline

- Structure : **Pipeline → Stages → Actions** (`Source`, `Build`, `Test`, `Deploy`, `Approval`, `Invoke`). Actions en séquentiel ou parallèle via `runOrder`.
- **Artifacts** stockés dans un **bucket S3** d'artifact store, chiffrés KMS. ⚠️ Le **versioning est obligatoire sur le bucket d'une action source S3** (pas sur l'artifact store).
- **Pipelines V2** : **triggers** avec filtres (branches, chemins de fichiers, **tags Git**, pull requests), **variables** au niveau du pipeline, **modes d'exécution** `SUPERSEDED` (défaut) / `QUEUED` / `PARALLEL`, **rollback de stage** (manuel ou automatique en cas d'échec).
- **Sources** : CodeCommit/S3 → détection via **EventBridge** (recommandé, vs polling qui est lent) ; GitHub → **CodeStar Connections** (webhook).
- **Manual approval** : action `Approval` + SNS pour notifier. IAM : `codepipeline:PutApprovalResult`.
- **Cross-account** : **KMS CMK** (pas la clé S3 par défaut) + bucket policy + rôle assumable dans le compte cible. Trio à retenir : *CMK + bucket policy + role*.
- **Cross-region** : bucket d'artifacts **dans chaque région**, CodePipeline réplique automatiquement.
- **Invoke/Lambda action** : pour tout ce qui n'existe pas nativement → la Lambda doit appeler `PutJobSuccessResult` / `PutJobFailureResult`.
- Monitoring : EventBridge sur les changements d'état (`FAILED`) → SNS/Lambda.

## 6. Stratégies de déploiement (transverse — très testé)

| Stratégie | Downtime | Coût | Rollback | Cas d'usage |
|---|---|---|---|---|
| All at once | Oui | Nul | Redéploiement | Dev/test |
| Rolling | Non (capacité réduite) | Nul | Lent | Prod tolérante |
| Rolling with additional batch | Non (capacité maintenue) | Faible | Lent | Prod, pas de perte de capacité |
| Immutable | Non | Élevé (double) | Rapide (terminer le nouvel ASG) | Prod critique |
| Blue/Green | Non | Double temporaire | **Instantané** (bascule DNS/LB) | Prod critique, test avant switch |
| Canary / Linear | Non | Faible | Rapide, exposition limitée | Réduire le blast radius |

**Elastic Beanstalk** — les policies : *All at once, Rolling, Rolling with additional batch, Immutable, Traffic splitting (canary)*.
Blue/Green EB = **swap CNAME** entre deux environnements (⚠️ pas une deployment policy, c'est une action manuelle/API `SwapEnvironmentCNAMEs`).
`.ebextensions/*.config` pour customiser la plateforme. Seules **All at once** et **Rolling** réduisent la capacité ; *Rolling with additional batch*, *Immutable* et *Traffic splitting* la maintiennent.
⚠️ **Piège EB + RDS** : une base créée **dans** l'environnement EB est supprimée avec lui → pour du Blue/Green ou de la prod, créer la RDS **en dehors** d'EB et passer la chaîne de connexion en variable d'environnement.
**Worker environment** + `cron.yaml` = tâches périodiques / traitement de fond via SQS.

**ECS** : rolling natif via `minimumHealthyPercent` / `maximumPercent`, ou blue/green via CodeDeploy (2 target groups + listener de test).

**Lambda** : versions immuables + **alias** avec **weighted routing** (ex. 10% sur v2). SAM/CFN : `AutoPublishAlias` + `DeploymentPreference` (type Canary/Linear, `Alarms`, `Hooks`).

## 7. CloudFormation (l'IaC de l'examen)

- **Change Sets** : prévisualiser l'impact d'une update avant de l'appliquer. Combiné aux **Stack Policies** (`Deny` sur `Update:Replace` pour les ressources critiques comme une RDS).
- **DeletionPolicy** (`Retain`, `Snapshot`, `Delete`) et **UpdateReplacePolicy** → protéger les données lors d'un remplacement.
- **CreationPolicy + cfn-signal** : attendre que N instances signalent « prêt » avant de marquer la stack CREATE_COMPLETE.
- **UpdatePolicy → AutoScalingRollingUpdate** : `MaxBatchSize`, `MinInstancesInService`, `PauseTime`, `WaitOnResourceSignals` → rolling update d'un ASG.
- **cfn-init / cfn-hup** : configuration et re-configuration à chaud des instances sur changement de metadata.
- **Nested stacks** = réutilisation de composants ; **StackSets** = déploiement multi-comptes / multi-régions (avec AWS Organizations, service-managed permissions).
- **Dynamic references** : `{{resolve:ssm:...}}`, `{{resolve:secretsmanager:...}}` → jamais de secret en dur.
- **Drift detection** : détecter les modifications hors IaC. **Custom resources** (Lambda) : pour tout ce que CFN ne supporte pas nativement (ex. vider un bucket S3 avant delete).
- Rollback : `DisableRollback` / `--on-failure` pour garder les ressources et debugger.

## 8. Artefacts & conteneurs

- **ECR** : scan d'images (basic à la poussée / enhanced via Inspector), **lifecycle policies** pour purger les vieilles images, réplication cross-region/cross-account, immutable tags pour éviter l'écrasement d'un tag.
- **S3** pour les artefacts : versioning + lifecycle + chiffrement KMS.

---

## Réflexes pour répondre aux questions

1. **« Minimal operational overhead »** → service managé natif (CodePipeline/CodeBuild) plutôt que Jenkins sur EC2 ou scripts custom.
2. **« Zero downtime + rollback immédiat »** → Blue/Green (CodeDeploy) ou alias Lambda pondéré.
3. **« Limiter l'impact d'un bug en prod »** → Canary/Linear + alarme CloudWatch + auto-rollback.
4. **« Empêcher un push direct sur main »** → IAM policy conditionnelle (pas une feature de CodeCommit).
5. **« Secrets dans le build »** → Secrets Manager / SSM Parameter Store référencés dans `buildspec`, jamais en variables d'environnement en clair.
6. **« Pipeline multi-comptes »** → KMS CMK + bucket policy + rôle cross-account.
7. **« Tester avant de basculer le trafic »** → hook `AfterAllowTestTraffic` (ECS) ou `BeforeAllowTraffic` (Lambda).
8. **« Détecter les changements manuels sur l'infra »** → CloudFormation drift detection (ou Config rules).
9. Si une réponse propose du **polling** ou du **cron**, il y a presque toujours une meilleure option **EventBridge**.

---

## Mémo dernière minute — les 5 points à réviser en priorité

### 1. Ordre des hooks `appspec`

**EC2 / On-prem** — `ApplicationStop` → `DownloadBundle`* → `BeforeInstall` → `Install`* → `AfterInstall` → `ApplicationStart` → `ValidateService`
Avec LB : `BeforeBlockTraffic` → `BlockTraffic`* → `AfterBlockTraffic` … puis … `BeforeAllowTraffic` → `AllowTraffic`* → `AfterAllowTraffic`
(*) = non scriptable, géré par l'agent.

**Lambda** — `BeforeAllowTraffic` → `AllowTraffic`* → `AfterAllowTraffic` (pas de phase Install)
**ECS** — `BeforeInstall` → `Install`* → `AfterInstall` → `AllowTestTraffic`* → `AfterAllowTestTraffic` → `BeforeAllowTraffic` → `AllowTraffic`* → `AfterAllowTraffic`
Ce sont des **fonctions Lambda** qui doivent renvoyer `PutLifecycleEventHookExecutionStatus`.
Mnémo : *le test se fait avant le trafic réel — `AfterAllowTestTraffic` (ECS), `BeforeAllowTraffic` (Lambda)*.

### 2. Stratégies de déploiement + Elastic Beanstalk

| Stratégie | Downtime | Capacité pendant le déploiement | Rollback |
|---|---|---|---|
| All at once | Oui | Réduite à 0 | Redéploiement |
| Rolling | Non | **Réduite** | Lent |
| Rolling with additional batch | Non | Maintenue | Lent |
| Immutable | Non | Maintenue (double) | Rapide |
| Blue/Green | Non | Double | **Instantané** |
| Canary / Linear | Non | Maintenue | Rapide, blast radius limité |

Policies EB : *All at once · Rolling · Rolling with additional batch · Immutable · Traffic splitting*.
⚠️ **Blue/Green n'est pas une policy EB** → c'est `SwapEnvironmentCNAMEs` entre deux environnements.
⚠️ Seules **All at once** et **Rolling** dégradent la capacité.
⚠️ RDS dans l'environnement EB = supprimée avec l'environnement → la sortir d'EB.

### 3. Cross-account CodePipeline

Trois éléments, toujours les trois :
1. **KMS CMK** (clé gérée par le client — la clé S3 par défaut ne marche pas cross-account) + key policy autorisant le compte cible.
2. **Bucket policy** sur le bucket d'artifacts autorisant le rôle du compte cible.
3. **Rôle IAM** dans le compte cible, assumable par le compte du pipeline (`sts:AssumeRole`), référencé par `roleArn` sur l'action.

Cross-**region** ≠ cross-account : il faut un **bucket d'artifacts par région**, la réplication est faite par CodePipeline.

### 4. Policies CloudFormation

| Attribut | Rôle | Point clé |
|---|---|---|
| `CreationPolicy` | Attendre N signaux avant CREATE_COMPLETE | Va avec **`cfn-signal`** + `Timeout` |
| `UpdatePolicy` | Comment mettre à jour un ASG | `AutoScalingRollingUpdate` : `MaxBatchSize`, `MinInstancesInService`, `PauseTime`, `WaitOnResourceSignals` |
| `DeletionPolicy` | Que faire au delete | `Retain` / `Snapshot` / `Delete` (défaut) |
| `UpdateReplacePolicy` | Que faire quand une update **remplace** la ressource | Sans lui, une RDS remplacée est supprimée |
| **Stack policy** | Protéger des ressources pendant les updates | `Deny` sur `Update:Replace` — s'applique **uniquement** aux updates, pas au delete. Dès qu'une stack policy existe, **tout est protégé par défaut** → il faut un `Allow` explicite sur le reste. Contre le delete → **termination protection** + `DeletionPolicy`. |

### 5. Deployment configurations (noms exacts)

**EC2 / On-prem** : `CodeDeployDefault.OneAtATime` · `HalfAtATime` · `AllAtOnce` (+ custom : min healthy hosts en % ou en nombre).

**Lambda** : `CodeDeployDefault.LambdaCanary10Percent5Minutes` · `...10Percent10Minutes` · `...10Percent15Minutes` · `...10Percent30Minutes` · `LambdaLinear10PercentEvery1Minute` · `...Every2Minutes` · `...Every3Minutes` · `...Every10Minutes` · `LambdaAllAtOnce`

**ECS** (liste plus courte) : `CodeDeployDefault.ECSCanary10Percent5Minutes` · `ECSCanary10Percent15Minutes` · `ECSLinear10PercentEvery1Minutes` · `ECSLinear10PercentEvery3Minutes` · `ECSAllAtOnce`.

Différence à ne pas rater : **Canary = 2 paliers** (X% pendant N minutes, puis 100%). **Linear = incréments égaux répétés** jusqu'à 100%.
