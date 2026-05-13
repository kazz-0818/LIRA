-- LIRA 監査ログ（Supabase SQL エディタで実行）
-- バックエンドは service_role キーで挿入する想定（RLS は anon からの読取のみ許可する例）

create table if not exists public.lira_audit_log (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  source text not null,
  detail jsonb not null default '{}'::jsonb
);

create index if not exists lira_audit_log_created_at_idx on public.lira_audit_log (created_at desc);

alter table public.lira_audit_log enable row level security;

-- 匿名キーからは読めない／書けない（必要ならダッシュボード用に SELECT のみ追加）
-- create policy "service only" ON public.lira_audit_log ...;
-- サーバーは service_role を使うため RLS をバイパスして挿入可能

comment on table public.lira_audit_log is 'LIRA API / LINE からの監査ログ（秘密は入れない）';
