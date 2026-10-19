# Core-4 temporal challenger research test

The structural core-4 remains frozen and unchanged.

Two pre-specified temporal research challengers are evaluated using the same 6-year rolling-origin protocol:

1. **1-year momentum**: inflow(t-1) - inflow(t-2)
2. **3-year trend slope**: slope across inflow(t-3), inflow(t-2), inflow(t-1)

Both use only information available before the forecast year.

These tests address the documented 2017-2019 failure mode, where migration levels fell for several consecutive years and the lagged-level model adjusted too slowly.

The results are research-only. They do not reopen structural variable selection and do not promote a temporal module to production.
