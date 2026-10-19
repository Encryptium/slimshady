import {useEffect, useState} from 'react';
import {AccessibilityInfo} from 'react-native';

export function useReducedMotion() {
  const [reduced, setReduced] = useState<boolean | undefined>(undefined);
  useEffect(() => {
    let active = true;
    AccessibilityInfo.isReduceMotionEnabled().then(value => { if (active) setReduced(value); }).catch(() => { if (active) setReduced(true); });
    const subscription = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduced);
    return () => { active = false; subscription.remove(); };
  }, []);
  return reduced;
}
