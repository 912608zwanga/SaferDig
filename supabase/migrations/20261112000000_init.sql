-- IntentGuard schema. Simulation only: no bank data is stored.
create extension if not exists pgcrypto;

create table public.intentions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  recipient_name text not null check (char_length(btrim(recipient_name)) between 1 and 120),
  amount numeric(12,2) not null check (amount > 0),
  currency text not null default 'ZAR' check (currency = 'ZAR'),
  purpose text not null check (char_length(btrim(purpose)) between 1 and 200),
  reference text check (reference is null or char_length(reference) <= 60),
  status text not null default 'pending'
    check (status in ('pending','verified_match','mismatch','needs_review','expired')),
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (expires_at > created_at)
);
create index intentions_user_created_idx on public.intentions (user_id, created_at desc);
create index intentions_user_status_idx on public.intentions (user_id, status);

create table public.verification_results (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  intention_id uuid not null references public.intentions(id) on delete cascade,
  recipient_match boolean not null,
  amount_match boolean not null,
  purpose_match boolean,
  recipient_review boolean not null default false,
  overall_result text not null check (overall_result in ('match','mismatch','needs_review')),
  created_at timestamptz not null default now()
);
create index verification_user_created_idx on public.verification_results (user_id, created_at desc);
create index verification_intention_idx on public.verification_results (intention_id);

create or replace function public.touch_updated_at() returns trigger
language plpgsql as $$ begin new.updated_at = now(); return new; end $$;
create trigger intentions_touch before update on public.intentions
  for each row execute function public.touch_updated_at();

alter table public.intentions enable row level security;
alter table public.verification_results enable row level security;

create policy intentions_select on public.intentions for select to authenticated
  using (user_id = (select auth.uid()));
create policy intentions_insert on public.intentions for insert to authenticated
  with check (user_id = (select auth.uid()));
create policy intentions_update on public.intentions for update to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy intentions_delete on public.intentions for delete to authenticated
  using (user_id = (select auth.uid()));

-- Results are written only through record_verification(); users can read and delete their own.
create policy verification_select on public.verification_results for select to authenticated
  using (user_id = (select auth.uid()));
create policy verification_delete on public.verification_results for delete to authenticated
  using (user_id = (select auth.uid()));

revoke all on public.intentions, public.verification_results from anon;
grant select, insert, update, delete on public.intentions to authenticated;
grant select, delete on public.verification_results to authenticated;

-- Atomically store a verification result and update the intention status.
-- SECURITY INVOKER: RLS still applies, so a user can only touch their own intention.
create or replace function public.record_verification(
  p_intention_id uuid, p_recipient_match boolean, p_amount_match boolean,
  p_purpose_match boolean, p_recipient_review boolean, p_overall text)
returns public.verification_results
language plpgsql security invoker set search_path = public as $$
declare r public.verification_results; new_status text;
begin
  new_status := case p_overall when 'match' then 'verified_match' else p_overall end;
  update public.intentions set status = new_status
   where id = p_intention_id and status in ('pending','mismatch','needs_review')
     and expires_at > now();
  if not found then raise exception 'intention_not_verifiable' using errcode = 'P0001'; end if;
  insert into public.verification_results
    (user_id, intention_id, recipient_match, amount_match, purpose_match, recipient_review, overall_result)
  values (auth.uid(), p_intention_id, p_recipient_match, p_amount_match, p_purpose_match, p_recipient_review, p_overall)
  returning * into r;
  return r;
end $$;
revoke all on function public.record_verification from public, anon;
grant execute on function public.record_verification to authenticated;
