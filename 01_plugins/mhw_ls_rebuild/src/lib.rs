//! Clean host shim: no legacy controller, private motion data or hit rewrites.
#![no_std]
use core::sync::atomic::{AtomicU32,Ordering};
use forge::log::prelude::*;
static BASE:AtomicU32=AtomicU32::new(0);
unsafe extern "C" {fn ml_install(base:u32)->u32;fn ml_pad_refresh();}

#[forge::hook(offset=0x003D_E064)]
fn sample_pad(object:u32)->u32{
    let value=original!(object);
    if BASE.load(Ordering::Relaxed)!=0 {unsafe{ml_pad_refresh();}}
    value
}
static VIB_INSTANCE:AtomicU32=AtomicU32::new(0);

#[forge::hook(offset=0x0086_EBA4)]
fn vib_play(this:u32){
    if this!=0 {VIB_INSTANCE.store(this,Ordering::Relaxed);}
    original!(this);
}

#[unsafe(no_mangle)]
extern "C" fn ml_vib_instance()->u32{VIB_INSTANCE.load(Ordering::Relaxed)}

#[forge::entry]
fn main(){
    let base=forge::mem::text_addr();
    #[cfg(all(not(ml_animation_preview),not(ml_world_combat)))]
    info!("[ml-rebuild] build=rebuild-b4 native_thrust_transitions=1 legacy_assets=0 scope=fade_step");
    #[cfg(ml_world_combat)]
    info!("[ml-rebuild] build=world-controller-dev1 scope=six_moves integration_validation_pending=1");
    #[cfg(ml_world_audio_probe)]
    info!("[ml-rebuild] audio-probe-only=1 independent_entry_deploy=0");
    #[cfg(ml_world_fx_probe)]
    info!("[ml-rebuild] fx-probe-only=1 independent_entry_deploy=0");
    #[cfg(ml_world_presentation)]
    info!("[ml-rebuild] presentation=world-layers-v102 world_audio=1 probe_mailbox=0");
    #[cfg(all(ml_animation_preview,not(ml_attachment_preview)))]
    info!("[ml-rebuild] build=body-preview-1 scope=animation_probe combat_ready=0");
    #[cfg(ml_attachment_preview)]
    info!("[ml-rebuild] build=attachment-preview-1 scope=attachment_probe combat_ready=0");
    let installed=unsafe{ml_install(base)};
    if installed==0 {error!("[ml-rebuild] native guards rejected; controller remains inactive");return;}
    BASE.store(base,Ordering::Relaxed);
    forge::install_hook!(base,sample_pad);
    forge::install_hook!(base,vib_play);
    info!("[ml-rebuild] installed; all styles; iai roll; sheath x1.50; iframe-2; native collision retained; rumble; chord-grace; lens-off");
}


unsafe extern "C" {fn forge_singleton_getAllInstances(out:*mut *mut u8,max:u32)->u32;}

#[unsafe(no_mangle)]
extern "C" fn ml_singletons(out:*mut u32,max:u32)->u32{
    let mut buf:[*mut u8;192]=[core::ptr::null_mut();192];
    let n=unsafe{forge_singleton_getAllInstances(buf.as_mut_ptr(),if max<192{max}else{192})} as usize;
    let n=if n>192{192}else{n};
    for i in 0..n{unsafe{*out.add(i)=buf[i] as u32;}}
    n as u32
}

unsafe extern "C" {fn forge_singleton_getInstanceByName(name:*const u8)->*mut u8;}

#[unsafe(no_mangle)]
extern "C" fn ml_singleton(name:*const u8)->u32{
    unsafe{forge_singleton_getInstanceByName(name) as u32}
}

#[repr(C)] struct RuSockAddr{sin_len:u8,sin_family:u8,sin_port:u16,sin_addr:[u8;4],sin_zero:[u8;8]}
#[repr(C)] #[derive(Clone,Copy)] struct RuSocket{fd:i32}
unsafe extern "C"{
    fn forge_socket_initDefault()->bool;
    fn forge_socket_create(domain:i32,ttype:i32,protocol:i32)->RuSocket;
    fn forge_socket_connect(socket:*const RuSocket,addr:*const RuSockAddr,len:usize)->i32;
    fn forge_socket_send(socket:*const RuSocket,buf:*const u8,len:usize,flags:i32)->isize;
}
static RUMBLE_FD:core::sync::atomic::AtomicI32=core::sync::atomic::AtomicI32::new(-1000);
const RUMBLE_PORT:u16=39876;
fn rumble_digits(buf:&mut[u8],mut at:usize,mut v:u32)->usize{
    let mut tmp=[0u8;10];let mut n=0;
    if v==0{buf[at]=b'0';return at+1;}
    while v>0{tmp[n]=b'0'+(v%10) as u8;v/=10;n+=1;}
    while n>0{n-=1;buf[at]=tmp[n];at+=1;}
    at
}
#[unsafe(no_mangle)]
extern "C" fn ml_rumble(on:u32,low:u32,high:u32)->u32{
    use core::sync::atomic::Ordering;
    unsafe{
        let mut fd=RUMBLE_FD.load(Ordering::Relaxed);
        if fd==-1000{
            forge_socket_initDefault();
            let s=forge_socket_create(2,2,0);
            fd=if s.fd>=0{
                let a=RuSockAddr{sin_len:0x10,sin_family:2,sin_port:RUMBLE_PORT.to_be(),sin_addr:[127,0,0,1],sin_zero:[0;8]};
                if forge_socket_connect(&s,&a,0x10)==0{s.fd}else{-1}
            }else{-1};
            RUMBLE_FD.store(fd,Ordering::Relaxed);
        }
        if fd<0{return 0;}
        let socket=RuSocket{fd};
        let mut buf=[0u8;40];let mut n=0;
        if on!=0{
            buf[0]=b'O';buf[1]=b'N';buf[2]=b' ';n=3;
            n=rumble_digits(&mut buf,n,low);buf[n]=b' ';n+=1;
            n=rumble_digits(&mut buf,n,high);
        }else{
            buf[0]=b'O';buf[1]=b'F';buf[2]=b'F';n=3;
        }
        buf[n]=b'\n';n+=1;
        let sent=forge_socket_send(&socket,buf.as_ptr(),n,0);
        if sent>0{1}else{0}
    }
}

#[cfg(ml_world_combat)]
static GAUGE_GLOW: AtomicU32 = AtomicU32::new(0);

#[cfg(ml_world_combat)]
#[unsafe(no_mangle)]
extern "C" fn ml_gauge_glow(value: u32) {
    GAUGE_GLOW.store(value, Ordering::Relaxed);
}

#[cfg(ml_world_combat)]
#[forge::imgui_free_render]
fn draw_gauge_glow() {
    use forge::imgui::{color::color, context, draw::DrawList};
    use forge::sys::imgui::ImVec2;
    let value = GAUGE_GLOW.swap(0, Ordering::Relaxed);
    if value == 0 { return; }
    let size = context::get_io().DisplaySize;
    let scale = (size.x / 640.0).min(size.y / 360.0);
    let wide = size.x / size.y > 16.0 / 9.0 + 0.01;
    let left = if wide { 0.0 } else { (size.x - 640.0 * scale) * 0.5 };
    let top = (size.y - 360.0 * scale) * 0.5;
    let width = 48.0 * (value >> 8) as f32 / 100.0;
    let dl = DrawList::foreground();
    dl.add_rect_filled(ImVec2::new(left+64.0*scale, top+38.0*scale),
        ImVec2::new(left+(64.0+width)*scale, top+40.0*scale),
        color(248,235,223,value as u8), 0.0);
}
