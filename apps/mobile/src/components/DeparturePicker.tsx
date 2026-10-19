import React, {useState} from 'react';
import {Modal, Pressable, ScrollView, StyleSheet, Text, View} from 'react-native';
import {Ionicons} from '@expo/vector-icons';
import {atlantaDate, clockLabel, departureISO} from '../lib/time';
const isoDay = (day: Date) => day.toISOString().slice(0, 10);
export function dateLabel(date: string) {
  if (date === atlantaDate()) return 'Today';
  return new Date(`${date}T12:00:00Z`).toLocaleDateString('en-US', {month: 'short', day: 'numeric', timeZone: 'UTC'});
}
export default function DeparturePicker({date, hour, onChange}: {date: string; hour: number; onChange: (date: string, hour: number) => void}) {
  const [open, setOpen] = useState(false);
  const [draftDate, setDraftDate] = useState(date);
  const [draftHour, setDraftHour] = useState(hour);
  const [month, setMonth] = useState(date.slice(0, 7));
  const [error, setError] = useState('');
  const first = new Date(`${month}-01T12:00:00Z`);
  const days = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate();
  const today = atlantaDate();
  function show() {setDraftDate(date); setDraftHour(hour); setMonth(date.slice(0, 7)); setError(''); setOpen(true);}
  function shift(delta: number) {setMonth(isoDay(new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + delta, 1))).slice(0, 7));}
  function apply() {try {departureISO(draftDate, draftHour); onChange(draftDate, draftHour); setOpen(false);} catch (e) {setError((e as Error).message);}}
  return <>
    <Pressable accessibilityRole="button" accessibilityLabel={`Change departure: ${dateLabel(date)} at ${clockLabel(hour)}`} onPress={show} style={({pressed})=>[s.trigger, pressed&&{backgroundColor:'#e6eddf'}]}>
      <View style={s.icon}><Ionicons name="calendar-outline" size={21} color="#315d43"/></View>
      <View style={{flex:1}}><Text style={s.eyebrow}>DEPARTURE · ATLANTA TIME</Text><Text style={s.value}>{dateLabel(date)} <Text style={s.muted}>at</Text> {clockLabel(hour)}</Text></View>
      <Ionicons name="chevron-down" size={17} color="#315d43"/>
    </Pressable>
    <Modal visible={open} transparent animationType="fade" onRequestClose={()=>setOpen(false)}>
      <View style={s.backdrop}><Pressable style={StyleSheet.absoluteFill} onPress={()=>setOpen(false)} accessibilityLabel="Dismiss departure picker"/><View accessibilityViewIsModal style={s.dialog}>
        <View style={s.header}><View><Text style={s.title}>When are you walking?</Text><Text style={s.muted}>Shade changes throughout the day.</Text></View><Pressable accessibilityRole="button" accessibilityLabel="Close departure picker" onPress={()=>setOpen(false)} style={s.arrow}><Ionicons name="close" size={22}/></Pressable></View>
        <ScrollView contentContainerStyle={{padding:22,gap:16}}>
          <View style={s.monthRow}><Pressable accessibilityRole="button" accessibilityLabel="Previous month" disabled={month<='2020-01'} onPress={()=>shift(-1)} style={s.arrow}><Ionicons name="chevron-back" size={20}/></Pressable><Text style={s.month}>{first.toLocaleDateString('en-US',{month:'long',year:'numeric',timeZone:'UTC'})}</Text><Pressable accessibilityRole="button" accessibilityLabel="Next month" disabled={month>='2035-12'} onPress={()=>shift(1)} style={s.arrow}><Ionicons name="chevron-forward" size={20}/></Pressable></View>
          <View style={s.grid}>{['S','M','T','W','T','F','S'].map((d,i)=><View key={`weekday-${i}`} style={s.cell}><Text style={s.weekday}>{d}</Text></View>)}
            {Array.from({length:first.getUTCDay()},(_,i)=><View key={`blank-${i}`} style={s.cell}/>)}
            {Array.from({length:days},(_,i)=>{const day=`${month}-${String(i+1).padStart(2,'0')}`;return <Pressable key={day} accessibilityRole="button" accessibilityLabel={new Date(`${day}T12:00:00Z`).toLocaleDateString('en-US',{dateStyle:'full',timeZone:'UTC'})} accessibilityState={{selected:day===draftDate}} onPress={()=>{setDraftDate(day);setError('');}} style={s.cell}><View style={[s.day,day===today&&s.today,day===draftDate&&s.selected]}><Text style={[s.dayText,day===draftDate&&s.white]}>{i+1}</Text></View></Pressable>;})}
          </View>
          <Pressable accessibilityRole="button" onPress={()=>{setDraftDate(today);setMonth(today.slice(0,7));setError('');}}><Text style={s.link}>Jump to today</Text></Pressable>
          <View style={s.timeHeader}><Text style={s.month}>Departure time</Text><Text style={s.muted}>Eastern time</Text></View>
          <ScrollView horizontal showsHorizontalScrollIndicator contentContainerStyle={{gap:7,paddingBottom:8}} contentOffset={{x:Math.max(0,(hour*2-1)*86),y:0}}>
            {Array.from({length:48},(_,i)=><Pressable key={i} accessibilityRole="button" accessibilityLabel={`Depart at ${clockLabel(i/2)}`} accessibilityState={{selected:draftHour===i/2}} onPress={()=>{setDraftHour(i/2);setError('');}} style={[s.timeChip,draftHour===i/2&&s.selected]}><Text style={[s.timeText,draftHour===i/2&&s.white]}>{clockLabel(i/2)}</Text></Pressable>)}
          </ScrollView>
          {!!error&&<Text accessibilityRole="alert" style={{color:'#a25935'}}>{error}</Text>}
        </ScrollView>
        <View style={s.footer}><Text style={s.summary}>{dateLabel(draftDate)} · {clockLabel(draftHour)}</Text><Pressable accessibilityRole="button" onPress={apply} style={s.apply}><Text style={s.white}>Apply departure</Text><Ionicons name="arrow-forward" color="white" size={17}/></Pressable></View>
      </View></View>
    </Modal>
  </>;
}
const s=StyleSheet.create({
  trigger:{flexDirection:'row',alignItems:'center',gap:11,padding:13,borderRadius:12,backgroundColor:'#eef2e8',borderWidth:1,borderColor:'#e1e7d9'},icon:{width:34,height:34,alignItems:'center',justifyContent:'center'},eyebrow:{fontSize:8.5,letterSpacing:1.2,color:'#748075',fontWeight:'700',marginBottom:5},value:{fontSize:13,color:'#193b2c',fontWeight:'600'},muted:{fontSize:12,color:'#748075',fontWeight:'400',lineHeight:19},backdrop:{flex:1,backgroundColor:'rgba(13,31,23,.38)',justifyContent:'center',alignItems:'center',padding:16},dialog:{backgroundColor:'#fbfcf8',width:'100%',maxWidth:420,maxHeight:'94%',borderRadius:22,overflow:'hidden',boxShadow:'0 20px 70px rgba(15,40,25,.18)'},header:{padding:22,flexDirection:'row',justifyContent:'space-between',alignItems:'center',borderBottomWidth:1,borderColor:'#e5e9df'},title:{fontSize:20,fontWeight:'600',color:'#193b2c',marginBottom:5},arrow:{padding:8},monthRow:{flexDirection:'row',alignItems:'center',justifyContent:'space-between'},month:{fontSize:14,fontWeight:'600',color:'#193b2c'},grid:{flexDirection:'row',flexWrap:'wrap'},cell:{width:'14.285714%',height:43,alignItems:'center',justifyContent:'center'},weekday:{fontSize:11,color:'#748075'},day:{width:36,height:36,borderRadius:18,alignItems:'center',justifyContent:'center'},today:{borderWidth:1,borderColor:'#8ba778'},selected:{backgroundColor:'#315d43'},dayText:{fontSize:13,color:'#193b2c'},white:{color:'white',fontWeight:'600',fontSize:13},link:{fontSize:12,color:'#315d43',fontWeight:'600'},timeHeader:{flexDirection:'row',justifyContent:'space-between',marginTop:3},timeChip:{borderRadius:9,paddingVertical:11,width:79,alignItems:'center',borderWidth:1,borderColor:'#dfe6d8'},timeText:{fontSize:12,color:'#315d43'},footer:{padding:20,borderTopWidth:1,borderColor:'#e5e9df',gap:14},summary:{fontSize:12,color:'#748075',textAlign:'center'},apply:{backgroundColor:'#193b2c',borderRadius:11,padding:15,flexDirection:'row',justifyContent:'center',alignItems:'center',gap:12},
});
