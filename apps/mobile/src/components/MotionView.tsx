import React, {useEffect, useState} from 'react';
import {Animated, Easing, Platform, type ViewProps} from 'react-native';
import {useReducedMotion} from '../hooks/useReducedMotion';
export default function MotionView({children, style, ...props}: ViewProps) {
  const reduced = useReducedMotion();
  const [progress] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (reduced === undefined) return;
    const animation = Animated.timing(progress, {toValue: 1, duration: reduced ? 0 : 240,
      easing: Easing.out(Easing.cubic), useNativeDriver: Platform.OS !== 'web'});
    animation.start();
    return () => animation.stop();
  }, [progress, reduced]);
  return <Animated.View {...props} style={[style, {opacity: progress,
    transform: [{translateY: progress.interpolate({inputRange: [0, 1], outputRange: [10, 0]})}]}]}>{children}</Animated.View>;
}
