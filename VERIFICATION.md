# Verified on September 26, 2026

Local service: `http://127.0.0.1:8765`, graph release `8c4e618985b9`.

| Check | Result |
| --- | --- |
| Python routing, shadow and real-source tests | 21 passed |
| Client timezone, calendar/DST and GPS projection checks | 7 passed |
| TypeScript | Passed |
| Expo lint | Passed |
| Expo Doctor | 21/21 passed |
| Web production export | Passed |
| iOS / Android Hermes bundle export | Both passed |
| Real API route test | Passed: Clough to Georgia Tech bookstore, detour cap, stairs exclusion, night, outside-coverage rejection |
| Chrome UI | Passed: search/example, route cards and map, save, evidence view, mobile viewport; no console errors |
| Foreground navigation | Started and stopped using simulated browser GPS; physical GPS not tested |
| Live weather | NWS response verified: 78°F, Sunny at time of check; outages handled explicitly |

The stair-free example produced a 895 m fastest route and a 971 m recommended route, with modeled cover increasing from 34.5% to 40.9%. These are model outputs, not field measurements. First-request latency varied from approximately 10 to 32 seconds during local testing with simultaneous builds; this is not a production load-test result.

Screenshots and actual API responses are in the ignored `artifacts/` directory. Reproduce them with the commands in README.md.

Not verified: installed native binaries, outdoor shade accuracy, real GPS drift/off-route behavior, background operation, Docker deployment or public hosting. EAS account/signing configuration is required to distribute native binaries. The Docker recipe has not been run on this Windows host.

Dependency audit currently reports 14 moderate transitive advisories in the Expo toolchain/router dependency tree (no high or critical findings). The suggested automatic fixes downgrade Expo/Router across major versions, so they were not blindly applied. Resolve supported upstream updates before a public production release.
