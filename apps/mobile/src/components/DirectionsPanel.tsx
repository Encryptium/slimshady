import React from 'react';
import {Modal, Pressable, ScrollView, StyleSheet, Text, View} from 'react-native';
import {Ionicons} from '@expo/vector-icons';
import type {Route} from '../lib/types';
import {distance, minutes} from '../lib/time';
import {instructionLabel} from '../lib/directions';
import MotionView from './MotionView';

type Props = {route: Route; destination?: string; docked: boolean; open: boolean; walking: boolean; stepIndex: number; onClose:()=>void; onOpen:()=>void; onStep:(coordinate:number[],index:number)=>void; onOverview:()=>void; onReport:()=>void; previewStep?:number};
export default function DirectionsPanel(p:Props) {
  const content = <>
    <View style={s.header}><View style={{flex:1}}><Text style={s.eyebrow}>DIRECTIONS</Text><Text style={s.title}>Step by step</Text></View><Pressable accessibilityRole="button" accessibilityLabel="Close directions" onPress={p.onClose} style={s.iconButton}><Ionicons name="close" size={20} color="#315d43"/></Pressable></View>
    <View style={s.summary}><View style={s.destinationIcon}><Ionicons name="flag-outline" size={19} color="#315d43"/></View><View style={{flex:1}}><Text numberOfLines={2} style={s.destination}>{p.destination||'Your destination'}</Text><Text style={s.muted}>{minutes(p.route.durationSeconds)} min · {distance(p.route.distanceMeters)} · {p.route.instructions.length} steps</Text></View></View>
    <View style={s.overview}><Text style={s.muted}>Select a step to see it on the map</Text><Pressable accessibilityRole="button" onPress={p.onOverview}><Text style={s.link}>Overview</Text></Pressable></View>
    <ScrollView key={p.route.id} showsVerticalScrollIndicator contentContainerStyle={{paddingHorizontal:16,paddingBottom:16}}>
      {p.route.instructions.map((step,i)=>{const active=p.previewStep===i||(p.walking&&p.stepIndex===i);const last=i===p.route.instructions.length-1;return <Pressable key={`${i}-${step.text}`} accessibilityRole="button" accessibilityLabel={`Step ${i+1}: ${step.text}`} accessibilityState={{selected:active}} onPress={()=>p.onStep(step.coordinate,i)} style={({pressed})=>[s.step,active&&s.activeStep,pressed&&{backgroundColor:'#eef2e8'}]}>
        <View style={s.track}><View style={[s.number,active&&{backgroundColor:'#315d43'}]}>{last?<Ionicons name="flag" size={13} color={active?'white':'#315d43'}/>:<Text style={[s.numberText,active&&{color:'white'}]}>{i+1}</Text>}</View>{!last&&<View style={s.line}/>}</View>
        <View style={{flex:1,paddingVertical:6}}><Text style={s.instruction}>{instructionLabel(step.text)}</Text><Text style={s.muted}>{i===0?'Start here':last?'Finish here':`${distance(step.atMeters)} from start`}</Text></View><Ionicons name="chevron-forward" size={13} color="#8b998b" style={{marginTop:12}}/>
      </Pressable>;})}
    </ScrollView>
    <View style={s.footer}><Ionicons name="walk-outline" size={16} color="#748075"/><Text style={[s.muted,{flex:1}]}>Follow actual paths and crossings.</Text><Pressable accessibilityRole="button" accessibilityLabel="Report a path or shade issue" onPress={p.onReport}><Ionicons name="flag-outline" size={17} color="#315d43"/></Pressable></View>
  </>;
  if(p.docked&&p.open)return <MotionView nativeID="directions-panel" style={s.dock}>{content}</MotionView>;
  return <>
    <Pressable accessibilityRole="button" accessibilityLabel="Show step-by-step directions" onPress={p.onOpen} style={[s.launcher,!p.docked&&{top:66}]}><Ionicons name="list-outline" color="#315d43" size={18}/><Text style={s.link}>Directions</Text><View style={s.count}><Text style={s.numberText}>{p.route.instructions.length}</Text></View></Pressable>
    {!p.docked&&<Modal visible={p.open} transparent animationType="slide" onRequestClose={p.onClose}><View style={s.backdrop}><Pressable style={StyleSheet.absoluteFill} onPress={p.onClose} accessibilityLabel="Dismiss directions"/><View accessibilityViewIsModal style={s.sheet}>{content}</View></View></Modal>}
  </>;
}
const s=StyleSheet.create({
  dock:{position:'absolute',right:24,top:82,bottom:90,width:310,maxHeight:650,backgroundColor:'#fbfcf8',borderRadius:18,borderWidth:1,borderColor:'#dce3d5',overflow:'hidden',boxShadow:'0 12px 40px rgba(25,59,44,.13)'},header:{padding:19,flexDirection:'row',alignItems:'center',borderBottomWidth:1,borderColor:'#e5e9df'},eyebrow:{fontSize:8,letterSpacing:1.4,fontWeight:'700',color:'#748075',marginBottom:6},title:{fontSize:21,fontWeight:'600',color:'#193b2c',letterSpacing:-.5},iconButton:{padding:8},summary:{flexDirection:'row',gap:11,padding:18,alignItems:'center',backgroundColor:'#f0f4ea'},destinationIcon:{height:35,width:35,borderRadius:18,backgroundColor:'#e1ead8',alignItems:'center',justifyContent:'center'},destination:{fontSize:12,fontWeight:'600',color:'#193b2c',lineHeight:18},muted:{fontSize:10.5,lineHeight:18,color:'#748075'},overview:{padding:16,flexDirection:'row',justifyContent:'space-between',gap:8},link:{fontSize:11,fontWeight:'600',color:'#315d43'},step:{flexDirection:'row',gap:10,paddingHorizontal:7,borderRadius:9,minHeight:70},activeStep:{backgroundColor:'#eaf0e2'},track:{alignItems:'center',paddingTop:5,width:28},number:{width:27,height:27,borderRadius:14,backgroundColor:'#eef2e8',alignItems:'center',justifyContent:'center'},numberText:{fontSize:10,color:'#315d43',fontWeight:'600'},line:{width:1,flex:1,backgroundColor:'#dce4d4',marginTop:4,marginBottom:4},instruction:{fontSize:12,lineHeight:19,color:'#193b2c',fontWeight:'500',marginBottom:3},footer:{padding:15,flexDirection:'row',alignItems:'center',gap:7,borderTopWidth:1,borderColor:'#e5e9df'},launcher:{position:'absolute',right:24,top:82,backgroundColor:'#fbfcf8',borderRadius:24,flexDirection:'row',gap:9,paddingVertical:10,paddingHorizontal:14,alignItems:'center',boxShadow:'0 4px 16px rgba(25,59,44,.12)'},count:{borderRadius:12,backgroundColor:'#e8eedf',paddingVertical:3,paddingHorizontal:7},backdrop:{flex:1,backgroundColor:'rgba(13,31,23,.3)',justifyContent:'flex-end'},sheet:{height:'78%',maxHeight:740,backgroundColor:'#fbfcf8',borderTopLeftRadius:24,borderTopRightRadius:24,overflow:'hidden',paddingBottom:18},
});
