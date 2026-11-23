/** Suggestions are relative to the current simulation time, in minutes. */
export function suggestOrderWindow(priority,now,ordinaryWidth){
 return priority==='urgent'||priority==='critical'?{earliest:now+5,deadline:now+15}:{earliest:now,deadline:now+ordinaryWidth};
}

/** The manual rush workflow validates the opening offset and window length. */
export function urgentWindowError(priority,now,earliest,deadline){
 if(priority!=='urgent'&&priority!=='critical')return '';
 if(!Number.isFinite(earliest)||!Number.isFinite(deadline))return '请输入有效的时间窗口。';
 if(earliest<now)return '最早服务开始不能早于当前模拟时间。';
 if(earliest>=deadline)return '最早服务开始必须早于签收完成截止。';
 const offset=priority==='critical'?10:15,length=priority==='critical'?15:20;
 if(earliest-now>=offset)return `${priority==='critical'?'特急':'紧急'}订单的窗口开始时间须距当前小于 ${offset} 分钟。`;
 if(deadline-earliest>=length)return `${priority==='critical'?'特急':'紧急'}订单的窗口长度须小于 ${length} 分钟。`;
 return '';
}
