-- ============================================================================
-- Fix: sign-in with Google (or a new email account) fails with
--   {"code":500,"error_code":"unexpected_failure", ...}
-- Supabase Auth calls public.hook_before_user_created as the role
-- supabase_auth_admin, which also needs USAGE on the schema the function is in.
-- TEST database only. Only grants; no data is read or changed.
-- ============================================================================
grant usage on schema public to supabase_auth_admin;
grant execute on function public.hook_before_user_created(jsonb) to supabase_auth_admin;
