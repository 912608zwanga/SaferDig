create policy verification_insert
on public.verification_results
for insert
to authenticated
with check (user_id = (select auth.uid()));

grant insert on public.verification_results to authenticated;
