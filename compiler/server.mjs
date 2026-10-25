// Stateless source compiler. Source text is parsed/bundled, never evaluated.
import http from 'node:http';
import crypto from 'node:crypto';
import path from 'node:path';
import {createRequire} from 'node:module';
import * as esbuild from 'esbuild';
const require=createRequire(import.meta.url),token=process.env.EVOLVYN_COMPILER_TOKEN||'';
const port=Number(process.env.PORT||8070);
if(!Number.isInteger(port)||port<1||port>65535)throw Error('Invalid compiler PORT');
let active=0;
const allowed=name=>typeof name==='string'&&/^[A-Za-z0-9_./-]+$/.test(name)&&!name.startsWith('/')&&name.split('/').every(part=>part&&part!=='.'&&part!=='..')&&/\.(jsx?|tsx?|css|json)$/.test(name);
const reply=(res,status,body)=>{res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(body));};
http.createServer(async(req,res)=>{
  if(req.url==='/health'&&req.method==='GET')return reply(res,token?200:503,{ready:!!token});
  const supplied=Buffer.from(String(req.headers['x-compiler-token']||'')),expected=Buffer.from(token);
  if(!token||supplied.length!==expected.length||!crypto.timingSafeEqual(supplied,expected))return reply(res,403,{detail:'Compiler authorization required'});
  if(req.url!=='/compile'||req.method!=='POST')return reply(res,404,{detail:'Not found'});
  if(active>=2)return reply(res,429,{detail:'Compiler capacity reached'});
  active++;
  try{
    let size=0;const chunks=[];
    for await(const chunk of req){size+=chunk.length;if(size>1_000_000)throw Error('Input limit');chunks.push(chunk);}
    const body=JSON.parse(Buffer.concat(chunks)),files=body.files;
    if(!files||Array.isArray(files)||Object.keys(body).some(k=>k!=='files')||Object.keys(files).length>64||Object.keys(files).some(k=>!allowed(k))||typeof files['main.jsx']!=='string'||Object.values(files).some(v=>typeof v!=='string'||v.length>300000))throw Error('Invalid source contract');
    const result=await esbuild.build({entryPoints:['virtual:main.jsx'],bundle:true,write:false,outdir:'/tmp/output',platform:'browser',format:'esm',logLevel:'silent',metafile:true,plugins:[{name:'fixed-source-contract',setup(build){
      build.onResolve({filter:/.*/},args=>{
        if(args.path==='virtual:main.jsx')return {path:'main.jsx',namespace:'product'};
        if(args.namespace==='product'){
          if(['react','react-dom','react-dom/client','lucide-react'].includes(args.path))return {path:require.resolve(args.path)};
          if(!args.path.startsWith('.'))return {errors:[{text:'Import outside the approved dependency contract'}]};
          const base=path.posix.normalize(path.posix.join(path.posix.dirname(args.importer),args.path));
          const name=[base,base+'.js',base+'.jsx',base+'.ts',base+'.tsx',base+'/index.jsx'].find(name=>allowed(name)&&Object.hasOwn(files,name));
          if(name)return {path:name,namespace:'product'};
          return {errors:[{text:'Import outside the approved product contract'}]};
        }
      });
      build.onLoad({filter:/.*/,namespace:'product'},args=>({contents:files[args.path],loader:args.path.endsWith('.json')?'json':args.path.endsWith('.css')?'css':args.path.endsWith('.tsx')?'tsx':args.path.endsWith('.ts')?'ts':'jsx'}));
    }}]});
    const bytes=result.outputFiles.reduce((n,f)=>n+f.contents.length,0);
    if(bytes>4_000_000)throw Error('Output limit');
    const hash=crypto.createHash('sha256');result.outputFiles.forEach(f=>hash.update(f.contents));
    reply(res,200,{status:'passed',bytes,sha256:hash.digest('hex'),checks:['React JSX and JSON imports bundled by esbuild '+esbuild.version,'CSS compiled','Source code was not executed; no runtime or business acceptance result is inferred']});
  }catch{reply(res,200,{status:'failed',detail:'Source contract or compilation failed. No application code was executed.'});}
  finally{active--;}
}).setTimeout(15000).listen(port,'0.0.0.0');
