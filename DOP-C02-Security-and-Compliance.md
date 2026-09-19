---
tags: [dop-c02, aws, devops, security, compliance, iam]
domaine: "6 — Security and Compliance (17% de l'examen)"
---

# DOP-C02 — Domaine 6 : Security and Compliance

> Poids : **17%**.
> Trois axes : (1) gérer les **identités et les accès** à grande échelle, (2) appliquer des **contrôles de sécurité automatisés** et protéger les données, (3) mettre en place la **surveillance et l'audit** de sécurité.
> Angle des questions : « quel service **détecte** ce problème, quel mécanisme l'**empêche**, et comment **automatiser** la remédiation sur **tous les comptes** ? »

---

## 1. IAM à grande échelle

### Logique d'évaluation (à connaître par cœur)

1. **Deny explicite** n'importe où → refusé. Toujours.
2. Sinon, l'action doit être autorisée par **chaque couche applicable** : **SCP** (et RCP) de l'Organization **ET** **permission boundary** (si présente) **ET** **session policy** (si présente) **ET** (identity policy **OU** resource policy).
3. Rien ne l'autorise → **deny implicite**.

| Mécanisme | Accorde des droits ? | Rôle |
|---|---|---|
| **Identity policy** | Oui | Droits d'un user/rôle |
| **Resource policy** (S3, KMS, SQS, Lambda…) | Oui | Qui peut accéder à la ressource, y compris **cross-compte** |
| **Permission boundary** | **Non** — plafond | Déléguer la création de rôles sans escalade de privilèges |
| **SCP** | **Non** — plafond | Garde-fou sur les comptes d'une OU (pas le compte de gestion) |
| **RCP** | **Non** — plafond | Garde-fou sur les **ressources** des comptes (data perimeter) |
| **Session policy** | **Non** — plafond | Réduire les droits d'une session assumée |

- **Pattern de délégation classique** : autoriser les devs à créer des rôles **uniquement** avec la condition `iam:PermissionsBoundary = arn:…/DevBoundary` → ils ne peuvent pas se donner plus que la boundary.
- **Cross-compte** : rôle dans le compte cible avec **trust policy** + `sts:AssumeRole` côté appelant. Pour KMS : **key policy** + IAM policy côté appelant. Pour S3 : **bucket policy** (+ key policy si SSE-KMS).
- **Conditions à reconnaître** : `aws:PrincipalOrgID` (restreindre à mon Organization), `aws:SourceVpce` / `aws:SourceVpc` (uniquement via un VPC endpoint), `aws:SecureTransport` (HTTPS obligatoire), `aws:MultiFactorAuthPresent`, `aws:RequestedRegion`, `aws:PrincipalTag` / `aws:ResourceTag` (**ABAC**).
- **IAM Identity Center** : SSO multi-comptes via **permission sets** → remplace les users IAM et les rôles cross-compte manuels. Source d'identité : annuaire interne, AD, IdP externe (SAML/SCIM).
- **Rôles plutôt que clés d'accès** : instance profile (EC2), task role (ECS), execution role (Lambda), **IAM Roles Anywhere** pour les serveurs on-prem.
- **IAM Access Analyzer** : findings d'**accès externe** (ressources partagées hors de la zone de confiance), **accès inutilisés** (rôles, clés, permissions), **validation de policies**, **génération de policy** à partir de l'activité CloudTrail → réponse à « moindre privilège ».
- **Credential report** (compte) et **access advisor / last accessed** (par entité) pour nettoyer les droits.

## 2. Le tableau de tri des services de sécurité

| Question posée | Service |
|---|---|
| Qui a fait quoi, quand, depuis où ? | **CloudTrail** |
| Quelle était la config de la ressource à l'instant T ? Est-elle conforme ? | **AWS Config** |
| Menace / comportement anormal / compromission (minage, IP malveillante, exfiltration) | **GuardDuty** |
| CVE / vulnérabilités logicielles (EC2, images ECR, Lambda) + exposition réseau | **Inspector** |
| Données sensibles (PII, cartes bancaires) dans S3 | **Macie** |
| Agréger tous les findings + contrôles de conformité (CIS, FSBP, PCI DSS) | **Security Hub** |
| Investiguer après un incident (graphe d'entités, cause racine) | **Detective** |
| Qui peut accéder à mes ressources depuis l'extérieur ? | **IAM Access Analyzer** |
| Collecter des preuves en continu pour un audit | **Audit Manager** |
| Télécharger les rapports de conformité d'AWS (SOC, ISO, PCI) | **AWS Artifact** |
| Gérer WAF / Shield / security groups / Network Firewall sur toute l'Org | **Firewall Manager** |

Détails qui font la différence :
- **GuardDuty** analyse **CloudTrail, VPC Flow Logs et logs DNS sans que tu aies à les activer** (sources fondamentales). Options : S3 Protection, EKS, **Runtime Monitoring**, **Malware Protection** (EBS, S3), RDS login activity, Lambda. Multi-comptes via **delegated administrator**. Il **détecte**, il ne corrige pas → EventBridge pour réagir.
- **Inspector** : scan **continu** et automatique ; EC2 via l'agent SSM (ou en mode agentless), ECR = **enhanced scanning**, Lambda.
- **Security Hub** : **nécessite AWS Config** pour ses contrôles. **Agrégation cross-région** vers une région principale, **delegated admin** pour l'Org, **automation rules** pour mettre à jour/supprimer des findings, **custom actions** → EventBridge pour déclencher une remédiation depuis la console.
- **Detective** ≠ GuardDuty : GuardDuty *trouve*, Detective *explique* (investigation).

## 3. Protection réseau

- **Security group** (stateful, allow uniquement, niveau ENI) vs **NACL** (stateless, allow + deny, niveau subnet → seul moyen de **bloquer une IP précise**).
- **VPC endpoints** : **gateway** (S3, DynamoDB — gratuits, via table de routage) vs **interface** (PrivateLink, la plupart des services, payants). **Endpoint policies** pour restreindre ce qui passe. Bucket policy avec `aws:SourceVpce` pour n'autoriser que le trafic via l'endpoint.
- **AWS WAF** : filtrage L7 sur CloudFront / ALB / API Gateway / AppSync. **Rate-based rules** (limiter une IP), managed rule groups (SQLi, XSS, IP reputation), géo-blocage.
- **Shield Standard** (gratuit, L3/L4) vs **Shield Advanced** (DDoS avancé, **Shield Response Team**, **protection contre les surcoûts** dus au scaling pendant une attaque).
- **Network Firewall** : inspection stateful/IDS/IPS au niveau VPC, filtrage de domaines sortants.
- **Firewall Manager** : imposer ces règles à **tous les comptes** de l'Org, y compris les nouveaux (prérequis : Organizations + Config + compte admin).

## 4. Protection des données

### KMS
- **AWS managed keys** (`aws/s3`…) : rotation automatique, **non partageables cross-compte**, key policy non modifiable. **Customer managed keys (CMK)** : key policy contrôlée, **rotation automatique optionnelle** (période configurable, 365 j par défaut), **seules utilisables cross-compte**.
- Clés à **matériel importé** : **pas de rotation automatique** → rotation manuelle (nouvelle clé + alias).
- **Key policy** = source d'autorité (sans elle, même l'admin IAM n'a pas accès). **Grants** pour des accès temporaires programmatiques.
- **Multi-Region keys** : même clé dans plusieurs régions → déchiffrer dans la région DR sans ré-chiffrer.
- **Supprimer une clé** = attente de 7 à 30 jours → pour stopper son usage immédiatement, la **désactiver**.

### S3
- Chiffrement par défaut **SSE-S3** ; **SSE-KMS** pour l'audit CloudTrail des usages de clé et le contrôle d'accès (+ **S3 Bucket Keys** pour réduire le coût KMS) ; **DSSE-KMS** (double couche) ; **SSE-C** (clé fournie par le client).
- Forcer HTTPS → bucket policy `Deny` si `aws:SecureTransport = false`. Forcer SSE-KMS → `Deny` sur `PutObject` sans le bon header.
- **Block Public Access** (au niveau compte), **Object Ownership = BucketOwnerEnforced** (désactive les ACL), **Object Lock** (WORM), **MFA Delete**, **Access Points**.

### Certificats et secrets
- **ACM** : renouvellement automatique des certificats **émis par ACM** (validation DNS recommandée). ⚠️ Les certificats **importés** ne sont **pas** renouvelés → surveiller l'expiration (**événements EventBridge/Health à partir de 45 jours**, Config rule `acm-certificate-expiration-check`).
- **Secrets Manager** : rotation native (Lambda), réplication multi-région, resource policy cross-compte. **Parameter Store SecureString** pour la config sensible sans rotation.
- **CloudHSM** : HSM dédié mono-tenant (FIPS 140 niveau 3), clés sous ton contrôle exclusif.

## 5. Automatiser la sécurité et la conformité

- **Chaîne type** : finding **GuardDuty / Security Hub / Config** → **EventBridge** → Lambda / SSM Automation / Step Functions → action (isoler l'instance en changeant son **security group**, révoquer une session, désactiver une clé, snapshot pour la forensique) → SNS.
- **Isoler une EC2 compromise** : remplacer le SG par un SG **sans règle** (forensique), **snapshot EBS**, retirer de l'ASG / détacher de l'ELB, garder l'instance (ne pas la terminer → perte des preuves).
- **Config** : conformance packs, **aggregator** multi-comptes, **remédiation automatique** SSM Automation. Control Tower **detective controls** = Config rules.
- **Preventive** (SCP, RCP, permission boundaries, IAM, CFN hooks) vs **detective** (Config, GuardDuty, Security Hub, Access Analyzer) vs **responsive** (EventBridge + automation).
- **Scanner le code et les images dans le pipeline** : CodeGuru Reviewer (secrets, défauts), **Inspector** sur ECR, et échec du build si vulnérabilités critiques.
- **Logs d'audit inviolables** : organization trail → bucket d'un **compte log archive** dédié, **log file validation**, **Object Lock**, SCP interdisant `StopLogging` / `DeleteTrail`.

---

## Réflexes pour répondre aux questions

1. **« Empêcher une action dans tous les comptes, même pour les admins »** → **SCP**.
2. **« Laisser les devs créer des rôles sans escalade de privilèges »** → **permission boundary** imposée par condition.
3. **« Restreindre l'accès à un bucket aux seuls comptes de mon Organization »** → `aws:PrincipalOrgID`.
4. **« Accès S3 uniquement depuis le VPC »** → VPC gateway endpoint + bucket policy `aws:SourceVpce`.
5. **« Instance qui communique avec une IP de minage de crypto »** → **GuardDuty** → EventBridge → isolation.
6. **« CVE dans mes images de conteneurs »** → **Inspector** (ECR enhanced scanning).
7. **« PII dans S3 »** → **Macie**.
8. **« Vue centrale des findings sécurité de tous les comptes et régions »** → **Security Hub** (delegated admin + agrégation cross-région).
9. **« Partager une clé KMS avec un autre compte »** → **customer managed key** + key policy (jamais une AWS managed key).
10. **« Certificat importé qui expire »** → EventBridge/Health (45 j) ou Config rule → notification / renouvellement.
11. **« Bloquer une IP malveillante »** → **NACL** (deny) ou **WAF** (si HTTP) — jamais un security group.
12. **« Imposer WAF / security groups sur tous les comptes, y compris futurs »** → **Firewall Manager**.
13. **« Moindre privilège à partir de l'usage réel »** → **IAM Access Analyzer** policy generation.

---

## Mémo dernière minute — les 5 points à réviser en priorité

### 1. Le tri détection
Qui/quand → **CloudTrail** · config/conformité → **Config** · menace → **GuardDuty** · CVE → **Inspector** · PII S3 → **Macie** · agrégation + standards → **Security Hub** · enquête → **Detective** · accès externe → **Access Analyzer**.

### 2. Plafonds vs droits
**SCP / RCP / permission boundary / session policy** = plafonds, n'accordent **rien**. **Identity / resource policies** = accordent. **Deny explicite** gagne toujours. SCP ne touche **pas** le compte de gestion.

### 3. KMS
Cross-compte → **CMK** + key policy. Matériel importé → **pas de rotation auto**. Stopper une clé tout de suite → **désactiver** (la suppression prend 7–30 jours). DR multi-région → **Multi-Region keys**.

### 4. Réseau
SG = stateful, allow seulement · NACL = stateless, **deny possible** · WAF = L7, rate-based · Shield Advanced = DDoS + SRT + protection des coûts · Firewall Manager = tout ça à l'échelle de l'Org.

### 5. Chaîne de remédiation sécurité
**Finding → EventBridge → Lambda/SSM Automation → isoler (SG vide) + snapshot + notifier.** Ne jamais terminer une instance compromise avant la forensique.
