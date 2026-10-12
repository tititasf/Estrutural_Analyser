'use strict';
importScripts('viewer_spatial.js?v=regional-ml-v1-i5');
self.onmessage=function(event) {
  const message=event.data;
  try {
    const index=CadSpatial.build(new Float64Array(message.buffer));
    self.postMessage({id:message.id,index},[index.segments.buffer,index.nodes.buffer,index.order.buffer]);
  } catch(error) { self.postMessage({id:message.id,error:String(error)}); }
};
