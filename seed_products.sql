-- =====================================================
-- SEED DATA — AI-Market Shop Bot
-- Adds categories, products, and item values (stock)
-- =====================================================

-- ── CATEGORIES ──────────────────────────────────────
INSERT INTO categories (name) VALUES
  ('🤖 AI Accounts'),
  ('🎬 Streaming'),
  ('🔐 VPN & Security'),
  ('🎮 Gaming')
ON CONFLICT (name) DO NOTHING;

-- ── GOODS (Products) ────────────────────────────────
-- Category: GPT (id=1)
INSERT INTO goods (name, price, description, category_id, warranty, note)
VALUES
  ('ChatGPT Plus', 14.99,
   'ChatGPT Plus subscription account. Includes GPT-4o, image generation, and advanced browsing.',
   1, '30 days', 'Change password immediately after purchase.')
ON CONFLICT (name) DO NOTHING;

-- Category: 🤖 AI Accounts
INSERT INTO goods (name, price, description, category_id, warranty, note)
SELECT
  v.name, v.price, v.description,
  c.id, v.warranty, v.note
FROM (VALUES
  ('Midjourney Basic',     9.99,  'Midjourney AI image generation — Basic plan. ~200 images/month.',          '🤖 AI Accounts', '30 days', 'Login via Discord. Do not share credentials.'),
  ('Midjourney Standard', 29.99, 'Midjourney Standard plan — unlimited relaxed generations.',                 '🤖 AI Accounts', '30 days', 'Login via Discord.'),
  ('Claude Pro',          19.99, 'Anthropic Claude Pro account. Access to Claude 3.5 Sonnet & Opus.',        '🤖 AI Accounts', '30 days', 'Change email after login.'),
  ('Perplexity Pro',       9.99, 'Perplexity AI Pro account. Unlimited AI search with GPT-4 & Claude.',      '🤖 AI Accounts', '14 days', 'Do not change phone number.')
) AS v(name, price, description, cat_name, warranty, note)
JOIN categories c ON c.name = v.cat_name
ON CONFLICT (name) DO NOTHING;

-- Category: 🎬 Streaming
INSERT INTO goods (name, price, description, category_id, warranty, note)
SELECT
  v.name, v.price, v.description,
  c.id, v.warranty, v.note
FROM (VALUES
  ('Netflix Premium',   14.99, 'Netflix Premium account — 4K UHD, 4 screens. Works worldwide.',            '🎬 Streaming', '30 days', 'Do not change the account password.'),
  ('Spotify Premium',    5.99, 'Spotify Premium individual account. Ad-free music, offline downloads.',     '🎬 Streaming', '30 days', 'Works on all devices.'),
  ('Disney+ Standard',   7.99, 'Disney+ Standard account — Full HD streaming, all Disney/Marvel/Star Wars.','🎬 Streaming', '30 days', 'Do not enable 2FA.'),
  ('YouTube Premium',    8.99, 'YouTube Premium account — ad-free videos, background play, YouTube Music.', '🎬 Streaming', '30 days', 'Works on mobile and desktop.')
) AS v(name, price, description, cat_name, warranty, note)
JOIN categories c ON c.name = v.cat_name
ON CONFLICT (name) DO NOTHING;

-- Category: 🔐 VPN & Security
INSERT INTO goods (name, price, description, category_id, warranty, note)
SELECT
  v.name, v.price, v.description,
  c.id, v.warranty, v.note
FROM (VALUES
  ('NordVPN 1 Month',   4.99, 'NordVPN Premium account — 1 month. 6200+ servers, 60+ countries.',  '🔐 VPN & Security', '30 days', 'Works on 6 devices simultaneously.'),
  ('ExpressVPN 1 Month',6.99, 'ExpressVPN 1-month account. Fastest VPN, 94 countries, 5 devices.', '🔐 VPN & Security', '30 days', 'Do not change account email.'),
  ('1Password Account', 3.99, '1Password individual account — unlimited passwords, 2FA storage.',   '🔐 VPN & Security', '30 days', 'Change master password on first login.')
) AS v(name, price, description, cat_name, warranty, note)
JOIN categories c ON c.name = v.cat_name
ON CONFLICT (name) DO NOTHING;

-- Category: 🎮 Gaming
INSERT INTO goods (name, price, description, category_id, warranty, note)
SELECT
  v.name, v.price, v.description,
  c.id, v.warranty, v.note
FROM (VALUES
  ('Xbox Game Pass Ultimate', 12.99, 'Xbox Game Pass Ultimate — 1 month. 100+ games + Xbox Live Gold.', '🎮 Gaming', '30 days', 'Use on your own Xbox or PC account.'),
  ('EA Play Pro',              8.99, 'EA Play Pro — 1 month. Access to FIFA, Battlefield, Apex, Sims.', '🎮 Gaming', '30 days', 'Works on PC via EA App only.'),
  ('Steam Wallet $10',         10.99,'Steam wallet code — $10 USD. Redeem on any Steam account.',       '🎮 Gaming', 'No warranty', 'Code delivered instantly after payment.')
) AS v(name, price, description, cat_name, warranty, note)
JOIN categories c ON c.name = v.cat_name
ON CONFLICT (name) DO NOTHING;

-- ── ITEM VALUES (Stock codes) ────────────────────────
-- ChatGPT Plus (finite stock)
INSERT INTO item_values (item_id, value, is_infinity)
SELECT g.id, v.val, false
FROM goods g, (VALUES
  ('chatgpt_plus_account_001:P@ssw0rd#2026!'),
  ('chatgpt_plus_account_002:SecurePass$99'),
  ('chatgpt_plus_account_003:MyAcc#ChatGPT4'),
  ('chatgpt_plus_account_004:Ultra$ecure2026'),
  ('chatgpt_plus_account_005:G3mini@Ultra!')
) AS v(val)
WHERE g.name = 'ChatGPT Plus'
ON CONFLICT (item_id, value) DO NOTHING;

-- Midjourney Basic (finite stock)
INSERT INTO item_values (item_id, value, is_infinity)
SELECT g.id, v.val, false
FROM goods g, (VALUES
  ('mj_basic_user001@mail.com:Mj@Secure2026!'),
  ('mj_basic_user002@mail.com:Artist$Pass99'),
  ('mj_basic_user003@mail.com:Image#Gen2026')
) AS v(val)
WHERE g.name = 'Midjourney Basic'
ON CONFLICT (item_id, value) DO NOTHING;

-- Midjourney Standard (finite stock)
INSERT INTO item_values (item_id, value, is_infinity)
SELECT g.id, v.val, false
FROM goods g, (VALUES
  ('mj_standard_user001@mail.com:Std$Pass2026!'),
  ('mj_standard_user002@mail.com:Art#Unlimited!')
) AS v(val)
WHERE g.name = 'Midjourney Standard'
ON CONFLICT (item_id, value) DO NOTHING;

-- Claude Pro (finite stock)
INSERT INTO item_values (item_id, value, is_infinity)
SELECT g.id, v.val, false
FROM goods g, (VALUES
  ('claude_pro_acc001@proton.me:Anthr0pic$2026'),
  ('claude_pro_acc002@proton.me:ClaudeP@ss#99'),
  ('claude_pro_acc003@proton.me:S0nnet$Ultra!')
) AS v(val)
WHERE g.name = 'Claude Pro'
ON CONFLICT (item_id, value) DO NOTHING;

-- Perplexity Pro (finite stock)
INSERT INTO item_values (item_id, value, is_infinity)
SELECT g.id, v.val, false
FROM goods g, (VALUES
  ('perp_pro_001@mail.com:Perpl3xityP@ss!'),
  ('perp_pro_002@mail.com:SearchAI$2026#')
) AS v(val)
WHERE g.name = 'Perplexity Pro'
ON CONFLICT (item_id, value) DO NOTHING;

-- Netflix Premium (finite stock)
INSERT INTO item_values (item_id, value, is_infinity)
SELECT g.id, v.val, false
FROM goods g, (VALUES
  ('netflix_user001@gmail.com:Netfl1x$Premium!'),
  ('netflix_user002@gmail.com:4KStream#2026!'),
  ('netflix_user003@gmail.com:BingeWatch$99'),
  ('netflix_user004@gmail.com:Ultra4K#Pass!')
) AS v(val)
WHERE g.name = 'Netflix Premium'
ON CONFLICT (item_id, value) DO NOTHING;

-- Spotify Premium (finite stock)
INSERT INTO item_values (item_id, value, is_infinity)
SELECT g.id, v.val, false
FROM goods g, (VALUES
  ('spotify_user001@gmail.com:Sp0tify$Music!'),
  ('spotify_user002@gmail.com:AdFree#2026!'),
  ('spotify_user003@gmail.com:Music$Stream99')
) AS v(val)
WHERE g.name = 'Spotify Premium'
ON CONFLICT (item_id, value) DO NOTHING;

-- Disney+ Standard (finite stock)
INSERT INTO item_values (item_id, value, is_infinity)
SELECT g.id, v.val, false
FROM goods g, (VALUES
  ('disney_user001@gmail.com:D1sney$Magic!'),
  ('disney_user002@gmail.com:Marvel#Stream99')
) AS v(val)
WHERE g.name = 'Disney+ Standard'
ON CONFLICT (item_id, value) DO NOTHING;

-- YouTube Premium (finite stock)
INSERT INTO item_values (item_id, value, is_infinity)
SELECT g.id, v.val, false
FROM goods g, (VALUES
  ('yt_premium001@gmail.com:Y0uTube$AdFree!'),
  ('yt_premium002@gmail.com:BackgndPlay#99!')
) AS v(val)
WHERE g.name = 'YouTube Premium'
ON CONFLICT (item_id, value) DO NOTHING;

-- NordVPN (finite stock)
INSERT INTO item_values (item_id, value, is_infinity)
SELECT g.id, v.val, false
FROM goods g, (VALUES
  ('nordvpn_user001@mail.com:N0rdVPN$Secure!'),
  ('nordvpn_user002@mail.com:VPN#Ultra2026!'),
  ('nordvpn_user003@mail.com:Secur3Net$99!')
) AS v(val)
WHERE g.name = 'NordVPN 1 Month'
ON CONFLICT (item_id, value) DO NOTHING;

-- ExpressVPN (finite stock)
INSERT INTO item_values (item_id, value, is_infinity)
SELECT g.id, v.val, false
FROM goods g, (VALUES
  ('expressvpn_u001@mail.com:Expr3ssVPN$2026!'),
  ('expressvpn_u002@mail.com:FastVPN#Ultra99!')
) AS v(val)
WHERE g.name = 'ExpressVPN 1 Month'
ON CONFLICT (item_id, value) DO NOTHING;

-- 1Password (finite stock)
INSERT INTO item_values (item_id, value, is_infinity)
SELECT g.id, v.val, false
FROM goods g, (VALUES
  ('1pass_user001@mail.com:0nePassw0rd$2026!'),
  ('1pass_user002@mail.com:Secur3Vault#99!')
) AS v(val)
WHERE g.name = '1Password Account'
ON CONFLICT (item_id, value) DO NOTHING;

-- Xbox Game Pass (finite stock)
INSERT INTO item_values (item_id, value, is_infinity)
SELECT g.id, v.val, false
FROM goods g, (VALUES
  ('xbox_gp_001@outlook.com:XboxGameP@ss2026!'),
  ('xbox_gp_002@outlook.com:Gam3Pass$Ultra!')
) AS v(val)
WHERE g.name = 'Xbox Game Pass Ultimate'
ON CONFLICT (item_id, value) DO NOTHING;

-- EA Play Pro (finite stock)
INSERT INTO item_values (item_id, value, is_infinity)
SELECT g.id, v.val, false
FROM goods g, (VALUES
  ('ea_play_001@ea.com:EAplay$Pro2026!'),
  ('ea_play_002@ea.com:Fif@#EAAccess99!')
) AS v(val)
WHERE g.name = 'EA Play Pro'
ON CONFLICT (item_id, value) DO NOTHING;

-- Steam Wallet $10 (key codes — no password needed, just the code)
INSERT INTO item_values (item_id, value, is_infinity)
SELECT g.id, v.val, false
FROM goods g, (VALUES
  ('STEAM-K4L1-B0T9-2026-XY1Z'),
  ('STEAM-M4RK-T3ST-2026-AB9C'),
  ('STEAM-SHOP-B0T0-2026-DE7F')
) AS v(val)
WHERE g.name = 'Steam Wallet $10'
ON CONFLICT (item_id, value) DO NOTHING;

-- ── SUMMARY ─────────────────────────────────────────
SELECT
  c.name AS category,
  g.name AS product,
  g.price,
  COUNT(iv.id) AS stock_count
FROM categories c
JOIN goods g ON g.category_id = c.id
LEFT JOIN item_values iv ON iv.item_id = g.id
GROUP BY c.name, g.name, g.price
ORDER BY c.name, g.name;
