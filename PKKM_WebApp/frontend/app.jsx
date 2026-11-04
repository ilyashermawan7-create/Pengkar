import React from 'react';
import { createRoot } from 'react-dom/client';
import Chart from 'chart.js/auto';
import * as XLSX from 'xlsx';
import {readParticipants} from './spreadsheet.mjs';
import StudentRecap from './StudentRecap.jsx';
import PrintReport from './PrintReport.jsx';
import {downloadReportPdf} from './reportPdf.mjs';
import MigrationPanel from './MigrationPanel.jsx';
import SurveySummary from './SurveySummary.jsx';
import surveySchema from '../survey_schema.json';
import {average} from './statistics.mjs';
import {calculateCsi,csiMethod} from './csi.mjs';
import {dashboardMetrics,activityGroup,activityGroupLabels} from './dashboardMetrics.mjs';
import {readSurveyResponses,normalizeName,downloadSatisfactionTemplate} from './migration.mjs';

    const { useState, useEffect, useRef } = React;

    function App() {
      // Sesi dipulihkan hanya setelah token diverifikasi oleh server.
      const [isLoggedIn, setIsLoggedIn] = useState(false);

      // State Form Login Depan
      const [loginUser, setLoginUser] = useState('');
      const [loginPass, setLoginPass] = useState('');
      const [showPass, setShowPass] = useState(false);
      const [loginError, setLoginError] = useState('');

      // 4 Menu Utama: 'dashboard' | 'laporan' | 'pengaturanAdmin' | 'pengaturan'
      const [activeNav, setActiveNav] = useState('dashboard');

      const [students, setStudents] = useState([]);
      const [masterStudents,setMasterStudents]=useState([]);
      const [pendingSurveys,setPendingSurveys]=useState([]);
      const [pendingParticipants,setPendingParticipants]=useState([]);
      const [activityPageSize,setActivityPageSize]=useState('10');
      const [activityPage,setActivityPage]=useState(1);
      const [activities, setActivities] = useState([]);
      const [surveys, setSurveys] = useState([]);
      const [adminList, setAdminList] = useState([]);
      const [token, setToken] = useState(() => sessionStorage.getItem('pkkm_token') || '');
      const [busy, setBusy] = useState(false);
      const [notice, setNotice] = useState('');
      const [editingId, setEditingId] = useState(null);
      const [participantRows, setParticipantRows] = useState([]);
      const [participantImportError, setParticipantImportError] = useState('');
      const [surveyRows, setSurveyRows] = useState([]);
      const [passwordForm, setPasswordForm] = useState({current_password:'',new_password:'',confirm:''});
      const [sidebarOpen, setSidebarOpen] = useState(false);
      const [surveyActivityId, setSurveyActivityId] = useState('');
      const api = async (path, options={}, authToken=token) => {
        const response = await fetch('/api' + path, {...options, headers: {
          ...(options.body ? {'Content-Type':'application/json'} : {}),
          ...(authToken ? {Authorization:'Bearer '+authToken} : {})
        }});
        const data = response.headers.get('content-type')?.includes('application/json') ? await response.json() : await response.text();
        if (!response.ok) {
          if (response.status === 401) {sessionStorage.removeItem('pkkm_token');setToken('');setIsLoggedIn(false);}
          throw new Error(typeof data.detail === 'string' ? data.detail : Array.isArray(data.detail) ? data.detail.map(e=>e.loc.slice(1).join('.')+': '+e.msg).join('; ') : 'Permintaan gagal ('+response.status+')');
        }
        return data;
      };
      const load = async (authToken=token) => {
        const data = await api('/dashboard', {}, authToken);
        setActivities(data.activities);setStudents(data.students);setSurveys(data.surveys);setMasterStudents(data.masterStudents||[]);setPendingSurveys(data.pendingSurveys||[]);setPendingParticipants(data.pendingParticipants||[]);
        setAdminList(data.adminList);setProfileData(data.profile);return data;
      };
      const run = async (operation) => {
        if (busy) return;
        setBusy(true);setNotice('');
        try {await operation();} catch(error) {setNotice(error.message);} finally {setBusy(false);}
      };
      // Filter State Dashboard
      const [searchNim, setSearchNim] = useState('');
      const [filterYear, setFilterYear] = useState('Semua Tahun');
      const [filterTw, setFilterTw] = useState('Semua Triwulan');
      const [filterCategory, setFilterCategory] = useState('Semua Kategori');

      // State Upload File di dalam Form Kegiatan
      const [importedParticipantFile, setImportedParticipantFile] = useState(null);

      const freshForm = () => {
        const date = new Date().toLocaleDateString('en-CA', {timeZone:'Asia/Jakarta'});
        return {namaKegiatan:'',tanggal:date,tahun:date.slice(0,4),triwulan:'TW'+(Math.floor((Number(date.slice(5,7))-1)/3)+1),
          program:'Pengembangan Karakter',jumlahPeserta:'',linkEvident:'',tempat:'',unitKerjasama:'',urusan:'Pengembangan karakter',
          kategori:'Pengembangan Karakter',jenis:'Pengembangan Karakter',pembicara:'',honor:'',takPanitia:10,takPeserta:5,laporan:'',
          targetSurveyKepuasan:'',evaluasiMateri:'',evaluasiNarasumber:'',evaluasiFasilitas:'',evaluasiDampak:'',catatanSurvey:''};
      };
      const [activityForm, setActivityForm] = useState(freshForm);
      // Form Tambah Admin Baru
      const [newAdmin, setNewAdmin] = useState({
        username: '',
        email: '',
        role: 'operator',
        nama: '',
        password: ''
      });

      const [profileData, setProfileData] = useState({username:'',nama:'',role:'viewer',email:'',instansi:'',kampus:'Telkom University'});
      const isAdmin = profileData.role === 'admin';
      const isOperator=profileData.role==='operator';
      const canManageAccounts=isAdmin||isOperator;
      const canWrite = ['admin','operator','pengkar','asrama'].includes(profileData.role);
      const canEdit = (act) => canWrite && (!['pengkar','asrama'].includes(profileData.role) || act.program === (profileData.role==='asrama'?'Asrama':'Pengembangan Karakter'));
      const roleLabel = role => ({admin:'Super Admin KKA',operator:'Operator KKA',verifier:'Verifikator Survey',pengkar:'Operator Pengkar',asrama:'Operator Asrama',viewer:'Viewer'}[role] || role);
      useEffect(()=>{if(isOperator)setNewAdmin(previous=>({...previous,role:'pengkar'}));},[isOperator]);
      useEffect(() => {
        if (!token) return;
        load(token).then(()=>setIsLoggedIn(true)).catch(error=>setLoginError(error.message));
      }, []);
      useEffect(()=>{if(!editingId)setActivityForm({...freshForm(),...(profileData.role==='asrama'?{program:'Asrama',kategori:'Pengkar Asrama',urusan:'Asrama'}:{})});},[profileData.role]);
      const filteredActivities = activities.filter(act => {
        const query=searchNim.trim().toLowerCase();
        return (!query || act.namaKegiatan.toLowerCase().includes(query) || students.some(s=>s.activityId===act.id && (s.nim.includes(query)||s.nama.toLowerCase().includes(query))))
          && (filterYear==='Semua Tahun'||act.tahun===filterYear)
          && (filterTw==='Semua Triwulan'||act.triwulan===filterTw)
          && (filterCategory==='Semua Kategori'||act.kategori===filterCategory);
      });
      useEffect(()=>{setActivityPage(1);},[searchNim,filterYear,filterTw,filterCategory,activities.length]);
      const activityLimit=activityPageSize==='all'?Math.max(1,filteredActivities.length):Number(activityPageSize);
      const activityPages=Math.max(1,Math.ceil(filteredActivities.length/activityLimit));
      const currentActivityPage=Math.min(activityPage,activityPages);
      const activityStart=(currentActivityPage-1)*activityLimit;
      const pagedActivities=filteredActivities.slice(activityStart,activityStart+activityLimit);
      const visibleIds = new Set(filteredActivities.map(a=>a.id));
      const filteredStudents=students.filter(s=>visibleIds.has(s.activityId));
      const filteredSurveys=surveys.filter(s=>visibleIds.has(s.activityId));
      const years=[...new Set([...activities.map(a=>a.tahun).filter(Boolean),String(new Date().getFullYear())])].sort().reverse();
      const categories=[...new Set(['Pengembangan Karakter','Pengkar Asrama','Wawasan Kebangsaan','Konseling','Kesehatan Mental','PPKPT',...activities.map(a=>a.kategori)])];
      const mean = average;
      const csi=calculateCsi(filteredSurveys);
      const surveyMetrics=csi.groups.map(group=>({label:group.label,divisor:group.divisor,val:group.percent===null?'—':group.percent.toFixed(1)+'%',skor:group.score===null?'—':group.score.toFixed(2),status:group.status}));
      const facultyCounts=Object.entries([...new Map(filteredStudents.map(s=>[s.nim||s.directoryId,s])).values()].reduce((acc,s)=>{const key=s.fakultas||'Belum diisi';acc[key]=(acc[key]||0)+1;return acc;},{})).sort((a,b)=>b[1]-a[1]);

      // Ref Chart Dashboard
      const pieChartRef = useRef(null);
      const barChartRef = useRef(null);
      const pieInstance = useRef(null);
      const barInstance = useRef(null);

      useEffect(() => {
        if (!isLoggedIn || activeNav !== 'dashboard') return;
        const palette=['#dc2626','#991b1b','#334155','#eab308','#06b6d4','#15803d','#2563eb'];
        const labels=[...new Set(filteredActivities.map(a=>a.kategori))];
        const chartYears=[...new Set(filteredActivities.map(a=>a.tahun||'Belum diisi'))].sort();
        if (pieChartRef.current) pieInstance.current=new Chart(pieChartRef.current,{type:'pie',data:{labels,datasets:[{data:labels.map(label=>filteredActivities.filter(a=>a.kategori===label).length),backgroundColor:palette,borderWidth:2,borderColor:'#fff'}]},options:{responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{position:'right',labels:{boxWidth:10,font:{size:9}}}}}});
        if (barChartRef.current) barInstance.current=new Chart(barChartRef.current,{type:'bar',data:{labels:chartYears,datasets:labels.map((label,index)=>({label,data:chartYears.map(year=>filteredActivities.filter(a=>(a.tahun||'Belum diisi')===year&&a.kategori===label).length),backgroundColor:palette[index%palette.length]}))},options:{responsive:true,maintainAspectRatio:false,animation:false,scales:{y:{beginAtZero:true,ticks:{precision:0}},x:{grid:{display:false}}},plugins:{legend:{position:'top',labels:{boxWidth:10,font:{size:10}}}}}});
        return ()=>{pieInstance.current?.destroy();barInstance.current?.destroy();};
      }, [isLoggedIn,activeNav,activities,students,searchNim,filterYear,filterTw,filterCategory]);
      const handleInitialLogin = async (e) => {
        e.preventDefault();setLoginError('');setBusy(true);
        try {
          const result=await api('/login',{method:'POST',body:JSON.stringify({username:loginUser,password:loginPass})},'');
          await load(result.token);sessionStorage.setItem('pkkm_token',result.token);setToken(result.token);
          setIsLoggedIn(true);setActiveNav('dashboard');setLoginPass('');
        } catch(error) {setLoginError(error.message);} finally {setBusy(false);}
      };
      const handleLogout = async () => {
        try {await api('/logout',{method:'POST'});} catch {}
        sessionStorage.removeItem('pkkm_token');setToken('');setIsLoggedIn(false);setActivities([]);setStudents([]);setMasterStudents([]);setPendingSurveys([]);setPendingParticipants([]);setSurveys([]);setAdminList([]);setNotice('');resetActivity();
      };

      // Lookup Mahasiswa
      const findStudent = (nim) => {
        if (!nim) return null;
        return masterStudents.find(s=>String(s.nim).trim()===String(nim).trim()) || students.find(s => String(s.nim).trim() === String(nim).trim());
      };

      const handleImportParticipantFile = async (e) => {
        const file=e.target.files[0];e.target.value='';if(!file)return;
        setParticipantImportError('');
        await run(async()=>{
          try {
            const {students:raw,duplicateCount,sheetName}=await readParticipants(file);
            const unique=raw.map(student=>{const known=findStudent(student.nim);return Object.fromEntries(['nim','nama','prodi','fakultas','kampus'].map(key=>[key,student[key]||known?.[key]||'']));});
            setParticipantRows(unique);
            setImportedParticipantFile({fileName:file.name,totalCount:unique.length,duplicateCount,sheetName});
            setActivityForm(prev=>({...prev,jumlahPeserta:unique.length}));
            setNotice(unique.length+' peserta unik siap disimpan bersama kegiatan.');
          } catch(error) {setParticipantImportError(error.message);throw error;}
        });
      };
      const handleImportSurveys = async (e) => {
        const file=e.target.files[0];e.target.value='';if(!file)return;
        await run(async()=>{
          const imported=await readSurveyResponses(file);
          const activityNames=[...new Set(imported.items.map(item=>item.namaKegiatan).filter(Boolean).map(normalizeName))];
          const expectedId=profileData.role==='verifier'?Number(surveyActivityId):editingId;
          if(imported.items.some(item=>item.activityId&&item.activityId!==expectedId))throw Error('ID kegiatan di file tidak cocok dengan form ini. Gunakan panel migrasi untuk mencocokkan kegiatan.');
          if(activityNames.length>1)throw Error('File memuat beberapa kegiatan. Gunakan panel Impor / Migrasi Data Lama.');
          const expectedName=profileData.role==='verifier'?activities.find(a=>a.id===Number(surveyActivityId))?.namaKegiatan:activityForm.namaKegiatan;
          if(expectedName&&activityNames.length&&activityNames[0]!==normalizeName(expectedName))throw Error('Nama kegiatan di file tidak sesuai kegiatan yang sedang dipilih. Gunakan panel migrasi untuk beberapa kegiatan.');
          const parsed=imported.items.map(item=>{
            const matched=participantRows.find(s=>s.nim===item.response.nim)||findStudent(item.response.nim);
            return {...item.response,nama:item.response.nama||matched?.nama||'',fakultas:item.response.fakultas||matched?.fakultas||'',kampus:item.response.kampus||matched?.kampus||''};
          });
          if(!expectedName&&imported.items[0].namaKegiatan)setActivityForm(prev=>({...prev,namaKegiatan:imported.items[0].namaKegiatan}));
          setSurveyRows(parsed);
          const average=mean(parsed.map(s=>s.skorTotal));
          setActivityForm(prev=>({...prev,targetSurveyKepuasan:average===null?'':average.toFixed(2),catatanSurvey:`Diimpor dari ${file.name}: ${parsed.length} respons.`}));
          setNotice(parsed.length+' respons survei siap disimpan.');
        });
      };
      const saveSurveyImport = async () => {
        await run(async()=>{
          if(!surveyActivityId || !surveyRows.length)throw Error('Pilih kegiatan dan impor berkas survei terlebih dahulu.');
          if(!confirm('Ganti seluruh respons survei kegiatan ini dengan '+surveyRows.length+' respons yang diimpor?'))return;
          await api('/dashboard/activities/'+surveyActivityId+'/surveys',{method:'PUT',body:JSON.stringify(surveyRows)});
          await load();setSurveyRows([]);setNotice('Respons survei berhasil disimpan.');
        });
      };
      const resetActivity = () => {setEditingId(null);setActivityForm({...freshForm(),...(profileData.role==='asrama'?{program:'Asrama',kategori:'Pengkar Asrama',urusan:'Asrama'}:{})});setParticipantRows([]);setSurveyRows([]);setImportedParticipantFile(null);setParticipantImportError('');};
      const editActivity = (act) => {
        setEditingId(act.id);setActivityForm({...freshForm(),...act,tanggal:act.tanggal||'',jumlahPeserta:act.jumlahPeserta??'',takPanitia:act.takPanitia??'',takPeserta:act.takPeserta??'',targetSurveyKepuasan:act.targetSurveyKepuasan??''});
        setParticipantRows(students.filter(s=>s.activityId===act.id&&s.nim));setSurveyRows(surveys.filter(s=>s.activityId===act.id));
        setImportedParticipantFile(null);setParticipantImportError('');setActiveNav('laporan');window.scrollTo(0,0);
      };
      const handleSaveActivity = async (e) => {
        e.preventDefault();await run(async()=>{
          const payload={...activityForm,tanggal:activityForm.tanggal||null,jumlahPeserta:activityForm.jumlahPeserta===''?null:Number(activityForm.jumlahPeserta),takPanitia:activityForm.takPanitia===''?null:Number(activityForm.takPanitia),takPeserta:activityForm.takPeserta===''?null:Number(activityForm.takPeserta),targetSurveyKepuasan:activityForm.targetSurveyKepuasan===''?null:Number(activityForm.targetSurveyKepuasan),participants:participantRows,surveys:surveyRows};
          await api('/dashboard/activities'+(editingId?'/'+editingId:''),{method:editingId?'PUT':'POST',body:JSON.stringify(payload)});
          await load();resetActivity();setNotice('Kegiatan berhasil disimpan di server.');
        });
      };
      const deleteActivity = async (act) => {
        if(!confirm('Hapus kegiatan '+act.namaKegiatan+' beserta peserta dan surveinya?'))return;
        await run(async()=>{await api('/activities/'+act.id,{method:'DELETE'});await load();if(editingId===act.id)resetActivity();setNotice('Kegiatan dihapus.');});
      };
      const handleCreateAdmin = async (e) => {
        e.preventDefault();await run(async()=>{
          await api('/dashboard/users',{method:'POST',body:JSON.stringify(newAdmin)});await load();
          setNewAdmin({username:'',email:'',role:isOperator?'pengkar':'operator',nama:'',password:''});setNotice('Akun baru berhasil dibuat dan dapat digunakan untuk login.');
        });
      };
      const handleDeleteAdmin = async (id,username) => {
        if(!confirm('Nonaktifkan akun '+username+'? Riwayat kegiatannya tetap disimpan.'))return;
        await run(async()=>{await api('/dashboard/users/'+id,{method:'DELETE'});await load();setNotice('Akun dinonaktifkan.');});
      };
      const saveProfile = async (e) => {
        e.preventDefault();await run(async()=>{await api('/profile',{method:'PUT',body:JSON.stringify(profileData)});await load();setNotice('Profil tersimpan. Gunakan username terbaru untuk login berikutnya.');});
      };
      const changePassword = async (e) => {
        e.preventDefault();await run(async()=>{
          if(passwordForm.new_password!==passwordForm.confirm)throw Error('Konfirmasi password tidak cocok.');
          await api('/profile/password',{method:'PUT',body:JSON.stringify(passwordForm)});
          await handleLogout();setPasswordForm({current_password:'',new_password:'',confirm:''});setLoginError('Password berhasil diubah. Silakan login kembali.');
        });
      };
      const exportActivities = () => {
        const safe=value=>typeof value==='string'&&/^[=+@-]/.test(value)?"'"+value:value;
        const rows=filteredActivities.map(a=>Object.fromEntries(Object.entries({...a,kelompokRekap:activityGroupLabels[activityGroup(a)]}).map(([k,v])=>[k,safe(v)])));
        const wb=XLSX.utils.book_new();XLSX.utils.book_append_sheet(wb,XLSX.utils.json_to_sheet(rows),'Kegiatan');XLSX.writeFile(wb,'Laporan_PKKM.xlsx');
      };

      // Unduh Template Mahasiswa
      const downloadStudentTemplate = () => {
        const sample = [
          { "Nama Lengkap": "Nama Mahasiswa Contoh", "NIM": "000000000001", "Program Studi": "S1 Informatika", "Fakultas": "Fakultas Informatika (FIF)", "Asal Kampus": "TELKOM UNIVERSITY - BANDUNG" }
        ];
        const ws = XLSX.utils.json_to_sheet(sample);
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, "Template_Mahasiswa");
        XLSX.writeFile(wb, "Template_Import_Mahasiswa_TelU.xlsx");
      };

      // Unduh Template Survei Kepuasan
      const downloadSurveyTemplate = () => downloadSatisfactionTemplate(activityForm.namaKegiatan || activities.find(a=>a.id===Number(surveyActivityId))?.namaKegiatan || '');

      // =========================================================================
      // 1. TAMPILAN AWALAN LOGIN (WAJIB LOGIN TERLEBIH DAHULU)
      // =========================================================================
      if (!isLoggedIn) {
        return (
          <div className="min-h-screen w-full flex flex-col md:flex-row bg-[#111315]">

            {/* SISI KIRI: BRANDING GELAP & BOKEH DENGAN LOGO TEL-U */}
            <div className="w-full md:w-3/5 min-h-[40vh] md:min-h-screen relative overflow-hidden bg-gradient-to-br from-[#121316] via-[#1a1b20] to-[#0d0e11] p-8 md:p-16 flex flex-col justify-between">

              <div className="absolute top-1/4 right-1/4 w-80 h-80 bg-red-600/20 rounded-full blur-[100px] pointer-events-none"></div>
              <div className="absolute bottom-1/4 left-1/4 w-96 h-96 bg-slate-500/15 rounded-full blur-[120px] pointer-events-none"></div>

              <div></div>

              <div className="relative z-10 space-y-4 max-w-xl">
                {/* Logo Bentuk Dua Segitiga Merah & Abu-abu */}
                <div className="relative w-24 h-24 mb-6">
                  <div className="absolute top-0 left-0 w-16 h-14 bg-[#EE2E24] rounded-tr-3xl rounded-bl-3xl shadow-lg"></div>
                  <div className="absolute bottom-0 right-0 w-16 h-14 bg-[#4A5568] rounded-tl-3xl rounded-br-3xl shadow-lg"></div>
                </div>

                <div className="space-y-1">
                  <p className="text-sm md:text-base font-normal text-slate-300">Selamat Datang di</p>
                  <h1 className="text-3xl md:text-5xl font-black text-white tracking-tight drop-shadow-md">
                    PKKM Telkom University
                  </h1>
                </div>

                <p className="text-xs md:text-sm text-slate-400 font-normal leading-relaxed pt-1">
                  Dasboard Pengembangan karakter Telkom University
                </p>

                <div className="pt-8 flex items-center gap-2 text-xs text-slate-400">
                  <span>Powered By:</span>
                  <div className="flex items-center gap-1 font-bold text-white tracking-wide text-sm">
                    <span className="w-2 h-2 rounded-full bg-[#EE2E24]"></span> PKKM<span className="font-light text-slate-400 text-xs">Framework</span>
                  </div>
                </div>
              </div>

              <div></div>
            </div>

            {/* SISI KANAN: FORM LOGIN SIGN IN */}
            <div className="w-full md:w-2/5 min-h-[60vh] md:min-h-screen bg-white flex items-center justify-center p-8 md:p-14">
              <div className="w-full max-w-md space-y-6">
                <div>
                  <h2 className="text-lg font-bold text-slate-900">PKKM Sign In</h2>
                </div>

                {loginError && (
                  <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg">
                    {loginError}
                  </div>
                )}

                <form onSubmit={handleInitialLogin} className="space-y-4 text-xs">
                  <div>
                    <label className="text-slate-600 block mb-1 font-medium" htmlFor="field-1">Username</label>
                    <input id="field-1" type="text"
                      required
                      value={loginUser}
                      onChange={(e) => setLoginUser(e.target.value)}
                      autoComplete="username" placeholder="Username akun Anda"
                      className="w-full px-4 py-3 bg-[#eef2fa] border border-[#dce3f1] rounded-lg text-slate-800 text-sm outline-none focus:border-[#c53030]"
                    />
                  </div>

                  <div>
                    <label htmlFor="login-password" className="text-slate-600 block mb-1 font-medium">Password</label>
                    <div className="relative">
                      <input
                        id="login-password" autoComplete="current-password" type={showPass ? "text" : "password"}
                        required
                        value={loginPass}
                        onChange={(e) => setLoginPass(e.target.value)}
                        placeholder="••••••••"
                        className="w-full px-4 py-3 bg-[#eef2fa] border border-[#dce3f1] rounded-lg text-slate-800 text-sm outline-none focus:border-[#c53030]"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPass(!showPass)}
                        className="absolute right-3 top-3.5 text-slate-400 hover:text-slate-600 text-xs font-semibold"
                      >
                        {showPass ? 'Sembunyi' : '👁'}
                      </button>
                    </div>
                  </div>

                  <div className="text-right">
                    <a href="#" onClick={(e) => {e.preventDefault();setLoginError("Hubungi administrator layanan untuk mereset password akun Anda.");}} className="text-[11px] text-slate-500 hover:text-slate-700">
                      Forgot password?
                    </a>
                  </div>

                  <button
                    type="submit" disabled={busy}
                    className="w-full py-3 bg-[#b91c1c] hover:bg-[#991b1b] text-white font-bold rounded-lg text-sm shadow-md transition-all tracking-wide"
                  >
                    Login
                  </button>
                </form>

                <div className="relative flex py-2 items-center">
                  <div className="flex-grow border-t border-slate-200"></div>
                  <span className="flex-shrink mx-4 text-slate-400 text-[10px] tracking-wider uppercase font-semibold">ATAU</span>
                  <div className="flex-grow border-t border-slate-200"></div>
                </div>

                <div className="space-y-2 text-center">
                  <p className="text-[10px] text-slate-400 leading-tight">
                    Login Google dan SSO Telkom University sedang dinonaktifkan sementara.
                  </p>
                  <button disabled className="w-full py-2.5 bg-slate-50 border border-slate-200 text-slate-300 font-medium rounded-lg text-xs flex items-center justify-center gap-2 cursor-not-allowed">
                    <span className="font-bold text-slate-300">G</span> Login Dengan Google
                  </button>
                  <button disabled className="w-full py-2.5 bg-slate-50 border border-slate-200 text-slate-300 font-medium rounded-lg text-xs flex items-center justify-center gap-2 cursor-not-allowed">
                    <span className="font-bold text-slate-300">🛡️</span> Login Dengan SSO Telkom University
                  </button>
                </div>
              </div>
            </div>


          </div>
        );
      }

      // =========================================================================
      // LOGIKA PERHITUNGAN METRIK DASHBOARD OTOMATIS & DINAMIS
      // =========================================================================
      const metrics=dashboardMetrics(filteredActivities);
      const totalPeserta=metrics.participants;
      const totalKegiatan=metrics.total;
      const totalPesertaUnik=new Set(filteredStudents.map(s=>s.nim).filter(Boolean)).size;
      const rasioMahasiswa=metrics.ratio.toFixed(2);
      const totalKegiatanKarakter=metrics.groups.karakter;
      const totalKegiatanPPKPT=metrics.groups.ppkpt;
      const totalKegiatanAsrama=metrics.groups.asrama;

      // =========================================================================
      // 2. TAMPILAN SETELAH LOGIN (PANEL DENGAN 4 MENU UTAMA)
      // =========================================================================
      return (
        <div className="min-h-screen flex bg-[#f8f9fa] text-slate-800">
          <PrintReport activities={filteredActivities} students={filteredStudents} surveys={filteredSurveys}
            filters={{year:filterYear,quarter:filterTw,category:filterCategory,search:searchNim}}
            preparedBy={profileData.nama} />

          {/* SIDEBAR KIRI */}
          <aside className={`${sidebarOpen ? "flex" : "hidden"} md:flex fixed inset-y-0 left-0 z-40 md:static w-64 bg-white border-r border-slate-200 flex flex-col justify-between shrink-0 shadow-sm min-h-screen`}>
            <div>
              {/* Branding sidebar */}
              <div className="p-6 border-b border-slate-100 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <div className="w-3.5 h-3.5 rounded-full bg-[#D71920]"></div>
                  <span className="font-extrabold text-xl text-slate-900 tracking-tight">satu</span>
                  <span className="font-light text-xs text-slate-400">framework</span>
                </div>
              </div>

              {/* 4 MENU UTAMA */}
              <div className="p-4 space-y-1 text-xs">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block px-3 py-2">
                  MENU NAVIGASI
                </span>

                <button
                  onClick={() => {setActiveNav('dashboard');setSidebarOpen(false);}}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl font-bold transition-all ${activeNav === 'dashboard' ? 'bg-[#fde8e8] text-[#D71920]' : 'text-slate-600 hover:bg-slate-50'}`}
                >
                  <span className="text-base">📊</span> Dashboard
                </button>

                <button
                  onClick={() => {setActiveNav('laporan');setSidebarOpen(false);}}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl font-bold transition-all ${activeNav === 'laporan' ? 'bg-[#fde8e8] text-[#D71920]' : 'text-slate-600 hover:bg-slate-50'}`}
                >
                  <span className="text-base">📝</span> Laporan
                </button>

                <button
                  disabled={!canManageAccounts} title={canManageAccounts?'':'Hanya Super Admin atau Operator KKA'} onClick={() => setActiveNav('pengaturanAdmin')}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl font-bold transition-all ${activeNav === 'pengaturanAdmin' ? 'bg-[#fde8e8] text-[#D71920]' : 'text-slate-600 hover:bg-slate-50'}`}
                >
                  <span className="text-base">👥</span> Pengaturan Admin
                </button>

                <button
                  onClick={() => {setActiveNav('pengaturan');setSidebarOpen(false);}}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl font-bold transition-all ${activeNav === 'pengaturan' ? 'bg-[#fde8e8] text-[#D71920]' : 'text-slate-600 hover:bg-slate-50'}`}
                >
                  <span className="text-base">⚙️</span> Pengaturan
                </button>
              </div>
            </div>

            {/* Logout di Sisi Bawah Sidebar */}
            <div className="p-4 border-t border-slate-100">
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-2 px-4 py-2.5 text-[#D71920] hover:bg-red-50 rounded-xl text-xs font-bold transition-all"
              >
                Log Out ➔
              </button>
            </div>
          </aside>

          {/* AREA KONTEN */}
          <div className="flex-1 flex flex-col min-h-screen overflow-x-hidden">

            {/* TOP HEADER DENGAN PROFILE: ADMIN KKA */}
            <header className="h-16 bg-white border-b border-slate-200 px-8 flex items-center justify-between shadow-sm sticky top-0 z-30">
              <div className="flex items-center gap-4">
                <button aria-label="Buka menu" onClick={()=>setSidebarOpen(!sidebarOpen)} className="text-slate-500 hover:text-slate-700 text-lg">☰</button>
                <div className="text-xs text-slate-400 font-medium">
                  <span className="hover:text-slate-600 cursor-pointer">Dit. KKA</span> &gt; <span className="text-slate-800 font-bold uppercase">{activeNav}</span>
                </div>
              </div>

              {/* PROFILE ADMIN KKA */}
              <div className="flex items-center gap-3 pl-4 border-l border-slate-200">
                <div className="w-9 h-9 rounded-full bg-[#1e293b] text-white flex items-center justify-center text-xs font-black shadow-sm">
                  {profileData.nama.slice(0,2).toUpperCase()}
                </div>
                <div className="text-left text-xs">
                  <span className="font-extrabold block text-slate-900 leading-tight">{profileData.nama}</span>
                  <span className="text-[11px] text-slate-400 font-medium">Telkom University</span>
                </div>
              </div>
            </header>

            {notice && <div role="status" className="mx-6 mt-4 p-3 bg-blue-50 border border-blue-200 text-blue-900 rounded-xl text-sm">{notice}</div>}
            {busy && <div role="status" className="mx-6 mt-2 text-sm text-slate-500">Memproses…</div>}
            {/* ========================================================================= */}
            {/* 1. MENU: DASHBOARD (PERSIS FOTO LAMPIRAN + ANALISIS SURVEY)               */}
            {/* ========================================================================= */}
            {activeNav === 'dashboard' && (
              <main className="p-6 md:p-8 space-y-6 max-w-[1440px] mx-auto w-full">

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

                  {/* SISI KIRI: FILTER PANEL (PERSIS GAMBAR) */}
                  <div className="lg:col-span-3 space-y-4">
                    <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4 text-xs">
                      <div>
                        <label className="font-bold text-slate-700 block mb-1" htmlFor="field-2">Cari Mahasiswa Berdasarkan NIM / Kegiatan</label>
                        <input id="field-2" type="text"
                          placeholder="Masukkan NIM atau Nama Kegiatan"
                          value={searchNim}
                          onChange={(e) => setSearchNim(e.target.value)}
                          className="w-full border border-slate-300 rounded-lg p-2.5 outline-none focus:border-[#D71920] text-slate-800"
                        />
                      </div>

                      <div>
                        <label className="font-bold text-slate-700 block mb-1" htmlFor="field-3">Tahun</label>
                        <select id="field-3" value={filterYear}
                          onChange={(e) => setFilterYear(e.target.value)}
                          className="w-full border border-slate-300 rounded-lg p-2.5 outline-none focus:border-[#D71920] bg-white font-medium"
                        >
                          <option value="Semua Tahun">Semua Tahun</option>
                          {years.map(year=><option key={year} value={year}>{year}</option>)}
                        </select>
                      </div>

                      <div>
                        <label className="font-bold text-slate-700 block mb-1" htmlFor="field-4">Triwulan</label>
                        <select id="field-4" value={filterTw}
                          onChange={(e) => setFilterTw(e.target.value)}
                          className="w-full border border-slate-300 rounded-lg p-2.5 outline-none focus:border-[#D71920] bg-white font-medium"
                        >
                          <option value="Semua Triwulan">Semua Triwulan</option>
                          <option value="TW1">TW1</option>
                          <option value="TW2">TW2</option>
                          <option value="TW3">TW3</option>
                          <option value="TW4">TW4</option>
                        </select>
                      </div>

                      <div className="pt-2">
                        <button
                          onClick={() => { setSearchNim(''); setFilterYear('Semua Tahun'); setFilterTw('Semua Triwulan'); setFilterCategory('Semua Kategori'); }}
                          className="w-full py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-bold text-center block transition-all"
                        >
                          Reset Filter
                        </button>
                      </div>

                      <div>
                        <label className="font-bold text-slate-700 block mb-1" htmlFor="field-5">Kategori</label>
                        <select id="field-5" value={filterCategory}
                          onChange={(e) => setFilterCategory(e.target.value)}
                          className="w-full border border-slate-300 rounded-lg p-2.5 outline-none focus:border-[#D71920] bg-white font-medium"
                        >
                          <option value="Semua Kategori">Semua Kategori</option>
                          {categories.map(category=><option key={category} value={category}>{category}</option>)}
                        </select>
                      </div>
                    </div>

                    <div className="bg-emerald-50 border border-emerald-200 p-4 rounded-2xl text-xs text-emerald-800 space-y-1">
                      <div className="flex items-center gap-1.5 font-bold">
                        <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
                        Database Terintegrasi
                      </div>
                      <p className="text-[11px] text-emerald-600">
                        Tersambung dengan {new Set(students.map(s=>s.nim)).size} mahasiswa teridentifikasi dari daftar peserta tersimpan.
                      </p>
                    </div>
                  </div>

                  {/* SISI KANAN: METRIK & CHART (PERSIS GAMBAR LAMPIRAN) */}
                  <div className="lg:col-span-9 space-y-6">

                    {/* BARIS METRIK UTAMA PERSIS FOTO */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm text-center">
                        <span className="text-xs font-semibold text-slate-500 block">Total Peserta</span>
                        <span className="text-3xl md:text-4xl font-black text-slate-900 mt-1 block">
                          {totalPeserta.toLocaleString('id-ID')}
                        </span>
                        <span className="text-[10px] text-slate-400 mt-0.5 block">Akumulasi kehadiran kegiatan sesuai filter</span>
                      </div>
                      <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm text-center">
                        <span className="text-xs font-semibold text-slate-500 block">Total Kegiatan</span>
                        <span className="text-3xl md:text-4xl font-black text-slate-900 mt-1 block">
                          {totalKegiatan.toLocaleString('id-ID')}
                        </span>
                        <span className="text-[10px] text-slate-400 mt-0.5 block">{totalKegiatan} dari {activities.length} kegiatan · sesuai filter aktif</span>
                      </div>
                    </div>

                    {/* BARIS SUB-METRIK PERSIS FOTO */}
                    <div className={`grid grid-cols-2 sm:grid-cols-3 ${metrics.groups.lainnya?'md:grid-cols-6':'md:grid-cols-5'} gap-3 text-center`}>
                      <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-sm">
                        <span className="text-[11px] font-medium text-slate-400 block">Peserta unik teridentifikasi (NIM)</span>
                        <span className="text-xl font-bold text-slate-800 mt-0.5 block">
                          {totalPesertaUnik.toLocaleString('id-ID')}
                        </span>
                      </div>
                      <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-sm">
                        <span className="text-[11px] font-medium text-slate-400 block">Rasio / target 45.000</span>
                        <span className="text-xl font-bold text-slate-800 mt-0.5 block">
                          {rasioMahasiswa}%
                        </span>
                        <span className="text-[10px] text-slate-400 block mt-1">Total Peserta ÷ 45.000 × 100%</span>
                      </div>
                      <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-sm">
                        <span className="text-[11px] font-medium text-slate-400 block">Kegiatan Karakter</span>
                        <span className="text-xl font-bold text-[#D71920] mt-0.5 block">
                          {totalKegiatanKarakter}
                        </span>
                      </div>
                      <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-sm">
                        <span className="text-[11px] font-medium text-slate-400 block">PPKPT</span>
                        <span className="text-xl font-bold text-blue-600 mt-0.5 block">
                          {totalKegiatanPPKPT}
                        </span>
                      </div>
                      <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-sm col-span-2 sm:col-span-1">
                        <span className="text-[11px] font-medium text-slate-400 block">Kegiatan Asrama</span>
                        <span className="text-xl font-bold text-emerald-600 mt-0.5 block">
                          {totalKegiatanAsrama}
                        </span>
                      </div>
                      {metrics.groups.lainnya>0&&<div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-sm"><span className="text-[11px] font-medium text-slate-400 block">Kegiatan Lainnya</span><span className="text-xl font-bold text-slate-800 mt-0.5 block">{metrics.groups.lainnya}</span></div>}
                    </div>
                    <div aria-label="Rincian perhitungan kegiatan" className="rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-600 space-y-1"><p>Rekap: {totalKegiatanKarakter} Karakter + {totalKegiatanPPKPT} PPKPT + {totalKegiatanAsrama} Asrama{metrics.groups.lainnya?` + ${metrics.groups.lainnya} Lainnya`:''} = <b>{totalKegiatan} kegiatan</b>.</p><p>Setiap kegiatan dihitung satu kali, dengan prioritas PPKPT → Asrama → Karakter. Semua angka mengikuti filter aktif; rincian kelompok tersedia pada ekspor Excel.</p>{metrics.unknownParticipants>0&&<p>{metrics.unknownParticipants} kegiatan belum memiliki jumlah peserta; nilai kosong tidak dianggap sebagai data peserta terisi.</p>}</div>

                    {/* DIAGRAM FAKULTAS & PIE KATEGORI (PERSIS GAMBAR) */}
                    <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
                      <div className="md:col-span-7 bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex flex-col justify-between">
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-xs font-bold text-slate-800">Jumlah Peserta Berdasarkan Fakultas</span>
                          <span className="text-[10px] text-slate-400">Sesuai filter</span>
                        </div>
                        <div className="space-y-2.5 my-auto py-2 text-xs">
                          {facultyCounts.length===0 && <p className="text-slate-400 py-6">Belum ada daftar peserta. Impor berkas peserta pada menu Laporan.</p>}
                          {facultyCounts.map(([name,count],index)=><div key={name}>
                            <div className="flex justify-between text-[11px] mb-1 font-semibold"><span>{name}</span><span className="text-[#D71920]">{count.toLocaleString('id-ID')} Mhs</span></div>
                            <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden"><div className={index===0?'bg-[#D71920] h-full rounded-full':'bg-slate-600 h-full rounded-full'} style={{width:(count/Math.max(1,...facultyCounts.map(f=>f[1]))*100)+'%'}} /></div>
                          </div>)}
                        </div>
                      </div>

                      <div className="md:col-span-5 bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex flex-col">
                        <span className="text-xs font-bold text-slate-800 mb-2">Kategori Kegiatan</span>
                        <div className="relative h-48 w-full">
                          <canvas ref={pieChartRef}></canvas>
                        </div>
                      </div>
                    </div>

                    {/* DIAGRAM BATANG TAHUN KE TAHUN (PERSIS GAMBAR) */}
                    <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                      <div className="flex justify-between items-center mb-4">
                        <span className="text-xs font-bold text-slate-800">Jumlah Kegiatan dari Tahun ke Tahun</span>
                        <span className="text-[10px] bg-slate-100 px-3 py-1 rounded-full text-slate-500">{[...new Set(filteredActivities.map(a=>a.tahun))].sort().join(" · ") || "Belum ada kegiatan"}</span>
                      </div>
                      <div className="relative h-56 w-full">
                        <canvas ref={barChartRef}></canvas>
                      </div>
                    </div>

                  </div>
                </div>

                {/* MODUL ANALISIS SURVEY KEPUASAN */}
                <div className="bg-white p-6 md:p-8 rounded-3xl border border-slate-200 shadow-sm space-y-6">
                  <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b pb-4">
                    <div>
                      <span className="px-2.5 py-1 bg-red-100 text-[#D71920] rounded-lg text-[10px] font-black uppercase tracking-wider">
                        Analisis Mutu Layanan Karakter
                      </span>
                      <h2 className="text-lg font-bold text-slate-900 mt-1">
                        Analisis Hasil Survey Kepuasan Kegiatan Mahasiswa
                      </h2>
                      <p className="text-xs text-slate-500">
                        Evaluasi komprehensif berdasarkan {filteredSurveys.length} respons mahasiswa peserta kegiatan pembinaan karakter.
                      </p>
                      <p className="text-xs text-slate-500 mt-1">{csi.responses} respons instrumen 20 pertanyaan · {csi.coverage}/20 pertanyaan memiliki nilai. {csi.provisional?'Hasil sementara; data belum lengkap.':'Seluruh pertanyaan terwakili.'}</p>
                      <details className="text-xs text-slate-500 mt-2"><summary className="cursor-pointer">Metode perhitungan CSI dan kategori</summary><p>{csiMethod}</p><p>Kategori operasional CSI: ≤35% tidak puas; &gt;35–50% kurang puas; &gt;50–65% cukup puas; &gt;65–80% puas; &gt;80% sangat puas. Ambang kategori adalah konvensi pelaporan, bukan standar universal.</p></details>
                    </div>
                    <div className="text-right bg-red-50 p-3 rounded-2xl border border-red-100">
                      <span className="text-[10px] font-bold text-[#D71920] block uppercase tracking-wider">CSI Bobot Setara{csi.provisional?' (sementara)':''}</span>
                      <span className="text-3xl font-black text-slate-900">{csi.percent===null?"—":csi.percent.toFixed(2)+"%"}</span><p className="text-xs text-slate-500">{csi.status} · MSS {csi.score===null?'—':csi.score.toFixed(2)} · Pembagi sesuai kelompok</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
                    {surveyMetrics.map((item, idx) => (
                      <div key={idx} className="bg-slate-50 p-4 rounded-2xl border border-slate-200">
                        <span className="text-xs font-semibold text-slate-500 block">{item.label}</span>
                        <div className="flex items-baseline justify-between mt-2">
                          <span className="text-2xl font-black text-slate-900">{item.val}</span>
                          <span className="text-xs bg-red-50 text-[#D71920] font-bold px-2 py-0.5 rounded">★ {item.skor} / {item.divisor}</span>
                        </div>
                        <span className="text-[10px] text-emerald-600 font-bold block mt-1">Status: {item.status}</span>
                      </div>
                    ))}
                  </div>

                </div>

              <SurveySummary surveys={filteredSurveys} activities={filteredActivities} />
              <StudentRecap rows={filteredStudents} activities={filteredActivities} />
              </main>
            )}

            {/* ========================================================================= */}
            {/* 2. MENU: LAPORAN (INPUT DATA KEGIATAN PERSIS FOTO + IMPORT MAHASISWA & SURVEY) */}
            {/* ========================================================================= */}
            {activeNav === 'laporan' && (
              <main className="p-6 md:p-8 space-y-6 max-w-[1440px] mx-auto w-full">

                {!isOperator&&<MigrationPanel activities={activities} role={profileData.role} api={api} reload={load} pendingSurveys={pendingSurveys} pendingParticipants={pendingParticipants} />}
                {isAdmin&&<StudentRecap mode="master" rows={masterStudents} activities={activities} />}
                <div className="bg-white border rounded-2xl p-4 space-y-3 text-xs no-print"><h3 className="font-bold">Filter Laporan</h3><div className="flex flex-wrap gap-3"><input aria-label="Cari laporan" placeholder="NIM / nama kegiatan" value={searchNim} onChange={e=>setSearchNim(e.target.value)} className="border rounded-lg p-2"/><select aria-label="Tahun laporan" value={filterYear} onChange={e=>setFilterYear(e.target.value)} className="border rounded-lg p-2"><option>Semua Tahun</option>{years.map(y=><option key={y}>{y}</option>)}</select><select aria-label="Triwulan laporan" value={filterTw} onChange={e=>setFilterTw(e.target.value)} className="border rounded-lg p-2"><option>Semua Triwulan</option>{['TW1','TW2','TW3','TW4'].map(q=><option key={q}>{q}</option>)}</select><select aria-label="Kategori laporan" value={filterCategory} onChange={e=>setFilterCategory(e.target.value)} className="border rounded-lg p-2"><option>Semua Kategori</option>{categories.map(c=><option key={c}>{c}</option>)}</select><button onClick={()=>{setSearchNim('');setFilterYear('Semua Tahun');setFilterTw('Semua Triwulan');setFilterCategory('Semua Kategori');}} className="border rounded-lg p-2">Reset Filter</button></div></div>
                {/* FORM INPUT KEGIATAN 16 FIELD MASTER PERSIS GAMBAR LAMPIRAN */}
                <div className="bg-white p-6 md:p-8 rounded-3xl border border-slate-200 shadow-sm space-y-6">
                  <div>
                    <h2 className="text-xl font-bold text-slate-900 tracking-tight">
                      Input Kegiatan Pengembangan Karakter (16 Field Master)
                    </h2>
                    <p className="text-xs text-slate-500 mt-1">
                      Data tersimpan di server dan otomatis tampil pada dashboard bersama.
                    </p>
                  </div>

                  {profileData.role==='verifier' && <section className="p-5 bg-amber-50 border border-amber-200 rounded-2xl space-y-3 text-xs"><h3 className="font-bold">Verifikasi / Impor Respons Survei</h3><label className="block">Kegiatan<select aria-label="Kegiatan survei" value={surveyActivityId} onChange={e=>{setSurveyActivityId(e.target.value);setSurveyRows([]);}} className="block w-full border rounded-xl p-3 mt-1"><option value="">Pilih kegiatan</option>{activities.map(a=><option key={a.id} value={a.id}>{a.namaKegiatan}</option>)}</select></label><input aria-label="Berkas survei verifikator" type="file" accept=".xlsx,.xls,.csv" onChange={handleImportSurveys} disabled={busy||!surveyActivityId}/><p>{surveyRows.length} respons siap disimpan.</p><button type="button" aria-label="Template Survey" title="20 pertanyaan asli. Lengkapi skor 1–5 sebelum mengimpor." onClick={downloadSurveyTemplate} className="border bg-white rounded-xl p-2 mr-2">Template Survey</button><button type="button" disabled={busy||!surveyRows.length} onClick={saveSurveyImport} className="bg-amber-600 text-white rounded-xl p-2">Simpan Respons Survei</button></section>}
                  {!canWrite && <p className="text-sm text-slate-500">Akun ini dapat membaca laporan. Input kegiatan tersedia untuk operator dan administrator.</p>}
                  {canWrite && <form onSubmit={handleSaveActivity} className="space-y-6 text-xs">
                    {editingId && <div className="p-3 bg-blue-50 text-blue-900 rounded-xl">Mengedit kegiatan #{editingId}. <button type="button" onClick={resetActivity}>Batalkan edit</button></div>}
                    <fieldset disabled={busy}>
                    <label className="font-bold block mb-1" htmlFor="field-6">Program / Hak Akses</label>
                    <select id="field-6" value={activityForm.program} onChange={e=>setActivityForm({...activityForm,program:e.target.value})} className="border rounded-xl p-3 mb-4 bg-white">
                      {profileData.role!=='asrama' && <option>Pengembangan Karakter</option>}{profileData.role!=='pengkar' && <option>Asrama</option>}
                    </select>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">

                      {/* Baris 1: Nama Kegiatan, Tanggal, Tahun & Triwulan (Persis Foto) */}
                      <div className="md:col-span-2">
                        <label className="font-bold text-slate-800 block mb-1" htmlFor="field-7">Nama Kegiatan</label>
                        <input id="field-7" type="text"
                          placeholder="Contoh: Webinar Relationship Management"
                          value={activityForm.namaKegiatan}
                          onChange={(e) => setActivityForm({ ...activityForm, namaKegiatan: e.target.value })}
                          className="w-full border border-slate-300 rounded-xl p-3 outline-none focus:border-[#D71920] text-sm"
                        />
                      </div>

                      <div>
                        <label className="font-bold text-slate-800 block mb-1" htmlFor="field-8">Tanggal Kegiatan</label>
                        <input id="field-8" type="date"
                          value={activityForm.tanggal}
                          onChange={(e) => {const date=e.target.value;setActivityForm({...activityForm,tanggal:date,tahun:date?date.slice(0,4):activityForm.tahun,triwulan:date?'TW'+(Math.floor((Number(date.slice(5,7))-1)/3)+1):''});}}
                          className="w-full border border-slate-300 rounded-xl p-3 outline-none focus:border-[#D71920] text-sm"
                        />
                      </div>

                      <div>
                        <label className="font-bold text-slate-800 block mb-1">Tahun & Triwulan</label>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={activityForm.tahun}
                            readOnly={!!activityForm.tanggal} onChange={event=>setActivityForm({...activityForm,tahun:event.target.value})} title="Otomatis dari tanggal jika ada; boleh diisi tanpa tanggal"
                            className="w-1/2 border border-slate-300 rounded-xl p-3 outline-none focus:border-[#D71920] text-sm font-semibold"
                          />
                          <select
                            aria-label="Triwulan kegiatan"
                            value={activityForm.triwulan}
                            disabled title="Otomatis dari tanggal kegiatan"
                            className="w-1/2 border border-slate-300 rounded-xl p-3 outline-none focus:border-[#D71920] bg-white font-bold text-sm"
                          >
                            <option value="">Belum diisi</option>
                            <option value="TW1">TW1</option>
                            <option value="TW2">TW2</option>
                            <option value="TW3">TW3</option>
                            <option value="TW4">TW4</option>
                          </select>
                        </div>
                      </div>

                      {/* Baris 2: Jumlah Peserta, Link Evident, Tempat Pelaksanaan (Persis Foto) */}
                      <div>
                        <label className="font-bold text-slate-800 block mb-1" htmlFor="field-9">Jumlah Peserta</label>
                        <input id="field-9" type="number"
                          placeholder="Contoh: 127"
                          value={activityForm.jumlahPeserta}
                          onChange={(e) => setActivityForm({ ...activityForm, jumlahPeserta: e.target.value })}
                          className="w-full border border-slate-300 rounded-xl p-3 outline-none focus:border-[#D71920] text-sm font-bold text-[#D71920]"
                        />
                      </div>

                      <div className="md:col-span-2">
                        <label className="font-bold text-slate-800 block mb-1" htmlFor="field-10">Link Evident (Google Drive / Sharepoint)</label>
                        <input id="field-10" type="text"
                          placeholder="https://... atau Dokumentasi Drive"
                          value={activityForm.linkEvident}
                          onChange={(e) => setActivityForm({ ...activityForm, linkEvident: e.target.value })}
                          className="w-full border border-slate-300 rounded-xl p-3 outline-none focus:border-[#D71920] text-sm"
                        />
                      </div>

                      <div>
                        <label className="font-bold text-slate-800 block mb-1" htmlFor="field-11">Tempat Pelaksanaan</label>
                        <input id="field-11" type="text"
                          placeholder="Zoom / TUCH / GSG / Manterawu"
                          value={activityForm.tempat}
                          onChange={(e) => setActivityForm({ ...activityForm, tempat: e.target.value })}
                          className="w-full border border-slate-300 rounded-xl p-3 outline-none focus:border-[#D71920] text-sm"
                        />
                      </div>

                      {/* FIELD BARU TERINTEGRASI: IMPORT DAFTAR MAHASISWA KE DALAM FORM KEGIATAN */}
                      <div className="md:col-span-4 p-4 bg-blue-50/70 border border-blue-200 rounded-2xl space-y-2">
                        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
                          <div>
                            <span className="font-bold text-blue-900 block text-xs">
                              📁 Import Daftar Nama Mahasiswa Peserta Kegiatan
                            </span>
                            <span className="text-[11px] text-blue-700">
                              Unggah spreadsheet peserta (Excel/CSV). Jumlah peserta terhitung otomatis berdasarkan NIM unik dalam berkas.
                            </span>
                          </div>
                          <div className="flex gap-2">
                            <label className="px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl text-xs cursor-pointer shadow-sm">
                              Pilih File Mahasiswa (.xlsx/.csv)
                              <input aria-label="Berkas peserta kegiatan" type="file" accept=".xlsx, .xls, .csv" className="hidden" onChange={handleImportParticipantFile} />
                            </label>
                            <button
                              type="button"
                              onClick={downloadStudentTemplate}
                              className="px-3 py-2 bg-white text-blue-700 border border-blue-200 rounded-xl text-xs font-semibold hover:bg-blue-50"
                            >
                              Unduh Template
                            </button>
                          </div>
                        </div>

                        {participantImportError && <p role="alert" className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-xl">{participantImportError} Daftar peserta sebelumnya tetap dipertahankan.</p>}
                        {participantRows.length>0 && <div aria-label="Pratinjau peserta kegiatan" className="p-3 bg-white border border-blue-200 rounded-xl space-y-2">
                          <p className="font-bold text-blue-900">{participantRows.length} mahasiswa unik {importedParticipantFile?'berhasil dibaca — belum disimpan':'terlampir pada kegiatan ini'}.</p>
                          {importedParticipantFile && <p className="text-blue-700">Berkas: {importedParticipantFile.fileName} · Sheet: {importedParticipantFile.sheetName}{importedParticipantFile.duplicateCount>0?` · ${importedParticipantFile.duplicateCount} baris NIM duplikat digabung`:''}.</p>}
                          <p className="text-slate-600">Lengkapi nama dan tanggal kegiatan, lalu klik <b>Simpan &amp; Publikasikan Kegiatan</b>. Sesudah tersimpan, mahasiswa muncul pada Rekap Data Mahasiswa di bawah dan dashboard.</p>
                          <div className="overflow-x-auto"><table className="w-full text-left"><thead><tr>{['NIM','Nama Mahasiswa','Program Studi','Fakultas','Kampus'].map(label=><th key={label} className="p-2">{label}</th>)}</tr></thead><tbody>{participantRows.slice(0,10).map(student=><tr key={student.nim} className="border-t"><td className="p-2 font-mono">{student.nim}</td><td className="p-2">{student.nama}</td><td className="p-2">{student.prodi||'—'}</td><td className="p-2">{student.fakultas||'—'}</td><td className="p-2">{student.kampus||'—'}</td></tr>)}</tbody></table></div>
                          {participantRows.length>10 && <p className="text-slate-500">Pratinjau 10 dari {participantRows.length} mahasiswa. Semua peserta akan disimpan.</p>}
                        </div>}
                        {!participantRows.length && !participantImportError && <p className="text-blue-800">Belum ada daftar mahasiswa terlampir. Mengisi angka Jumlah Peserta saja tidak membuat rekap nama/NIM. Pilih berkas peserta untuk mengisi daftar.</p>}
                      </div>

                      {/* Baris 3: Unit Kerjasama, Urusan, Kategori, Jenis Kegiatan (Persis Foto) */}
                      <div>
                        <label className="font-bold text-slate-800 block mb-1" htmlFor="field-12">Unit Kerjasama</label>
                        <input id="field-12" type="text"
                          placeholder="IPK / Telkomedika / Senior Resident"
                          value={activityForm.unitKerjasama}
                          onChange={(e) => setActivityForm({ ...activityForm, unitKerjasama: e.target.value })}
                          className="w-full border border-slate-300 rounded-xl p-3 outline-none focus:border-[#D71920] text-sm"
                        />
                      </div>

                      <div>
                        <label className="font-bold text-slate-800 block mb-1" htmlFor="field-13">Urusan</label>
                        <input id="field-13" type="text"
                          value={activityForm.urusan}
                          onChange={(e) => setActivityForm({ ...activityForm, urusan: e.target.value })}
                          className="w-full border border-slate-300 rounded-xl p-3 outline-none focus:border-[#D71920] text-sm"
                        />
                      </div>

                      <div>
                        <label className="font-bold text-slate-800 block mb-1" htmlFor="field-14">Kategori</label>
                        <select id="field-14" value={activityForm.kategori}
                          onChange={(e) => setActivityForm({ ...activityForm, kategori: e.target.value })}
                          className="w-full border border-slate-300 rounded-xl p-3 outline-none focus:border-[#D71920] bg-white font-bold text-sm"
                        >
                          {categories.map(category=><option key={category} value={category}>{category}</option>)}
                        </select>
                      </div>

                      <div>
                        <label className="font-bold text-slate-800 block mb-1" htmlFor="field-15">Jenis Kegiatan</label>
                        <input id="field-15" type="text"
                          placeholder="Pengembangan Karakter / Pelatihan / Seminar"
                          value={activityForm.jenis}
                          onChange={(e) => setActivityForm({ ...activityForm, jenis: e.target.value })}
                          className="w-full border border-slate-300 rounded-xl p-3 outline-none focus:border-[#D71920] text-sm"
                        />
                      </div>

                      {/* Baris 4: Pembicara, Honor, TAK Panitia, TAK Peserta (Persis Foto) */}
                      <div>
                        <label className="font-bold text-slate-800 block mb-1" htmlFor="field-16">Pembicara / Narasumber</label>
                        <input id="field-16" type="text"
                          placeholder="Nama Pemateri & Gelar"
                          value={activityForm.pembicara}
                          onChange={(e) => setActivityForm({ ...activityForm, pembicara: e.target.value })}
                          className="w-full border border-slate-300 rounded-xl p-3 outline-none focus:border-[#D71920] text-sm"
                        />
                      </div>

                      <div>
                        <label className="font-bold text-slate-800 block mb-1" htmlFor="field-17">Honor Pembicara (Rp)</label>
                        <input id="field-17" type="text"
                          placeholder="Rp 0"
                          value={activityForm.honor}
                          onChange={(e) => setActivityForm({ ...activityForm, honor: e.target.value })}
                          className="w-full border border-slate-300 rounded-xl p-3 outline-none focus:border-[#D71920] text-sm"
                        />
                      </div>

                      <div>
                        <label className="font-bold text-slate-800 block mb-1" htmlFor="field-18">TAK Panitia</label>
                        <input id="field-18" type="number"
                          value={activityForm.takPanitia}
                          onChange={(e) => setActivityForm({ ...activityForm, takPanitia: e.target.value })}
                          className="w-full border border-slate-300 rounded-xl p-3 outline-none focus:border-[#D71920] text-sm"
                        />
                      </div>

                      <div>
                        <label className="font-bold text-slate-800 block mb-1" htmlFor="field-19">TAK Peserta</label>
                        <input id="field-19" type="number"
                          value={activityForm.takPeserta}
                          onChange={(e) => setActivityForm({ ...activityForm, takPeserta: e.target.value })}
                          className="w-full border border-slate-300 rounded-xl p-3 outline-none focus:border-[#D71920] text-sm"
                        />
                      </div>

                      {/* SEKSI BARU: FIELD KHUSUS SURVEY KEPUASAN & EVALUASI KEGIATAN */}
                      <div className="md:col-span-4 p-5 bg-amber-50/60 border border-amber-200 rounded-2xl space-y-4">
                        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-amber-200 pb-2">
                          <div>
                            <span className="font-bold text-amber-900 block text-xs">
                              ⭐ Instrumen Evaluasi & Survey Kepuasan Kegiatan
                            </span>
                            <span className="text-[11px] text-amber-700">
                              Input target/capaian mutu survey kepuasan peserta mahasiswa untuk kegiatan ini.
                            </span>
                          </div>
                          <div className="flex gap-2">
                            <label className="px-3.5 py-1.5 bg-amber-500 hover:bg-amber-600 text-white font-bold rounded-xl text-xs cursor-pointer shadow-sm">
                              Import Nilai Survey Mahasiswa
                              <input aria-label="Berkas survei kegiatan" type="file" accept=".xlsx, .xls, .csv" className="hidden" onChange={handleImportSurveys} />
                            </label>
                            <button
                              type="button"
                              aria-label="Template Survey" title="20 pertanyaan asli. Lengkapi skor 1–5 sebelum mengimpor." onClick={downloadSurveyTemplate}
                              className="px-3 py-1.5 bg-white text-amber-800 border border-amber-200 rounded-xl text-xs font-semibold hover:bg-amber-50"
                            >
                              Template Survei Kepuasan
                            </button>
                          </div>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3">
                          <div>
                            <label className="font-bold text-amber-900 block mb-1" htmlFor="field-20">Skor Indeks Kepuasan (1-5)</label>
                            <input id="field-20" type="text"
                              placeholder="Belum ada nilai"
                              value={activityForm.targetSurveyKepuasan}
                              onChange={(e) => setActivityForm({ ...activityForm, targetSurveyKepuasan: e.target.value })}
                              className="w-full border border-amber-300 rounded-xl p-2.5 bg-white font-bold text-amber-900 outline-none"
                            />
                          </div>
                          <div>
                            <label className="font-bold text-amber-900 block mb-1" htmlFor="field-21">Evaluasi Materi</label>
                            <select id="field-21" value={activityForm.evaluasiMateri}
                              onChange={(e) => setActivityForm({ ...activityForm, evaluasiMateri: e.target.value })}
                              className="w-full border border-amber-300 rounded-xl p-2.5 bg-white outline-none"
                            >
                              <option value="">Belum dievaluasi</option>
                              <option>Sangat Baik (95%)</option>
                              <option>Baik (85%)</option>
                              <option>Cukup (75%)</option>
                            </select>
                          </div>
                          <div>
                            <label className="font-bold text-amber-900 block mb-1" htmlFor="field-22">Evaluasi Narasumber</label>
                            <select id="field-22" value={activityForm.evaluasiNarasumber}
                              onChange={(e) => setActivityForm({ ...activityForm, evaluasiNarasumber: e.target.value })}
                              className="w-full border border-amber-300 rounded-xl p-2.5 bg-white outline-none"
                            >
                              <option value="">Belum dievaluasi</option>
                              <option>Sangat Baik (98%)</option>
                              <option>Baik (88%)</option>
                              <option>Cukup (78%)</option>
                            </select>
                          </div>
                          <div>
                            <label className="font-bold text-amber-900 block mb-1" htmlFor="field-23">Evaluasi Fasilitas</label>
                            <select id="field-23" value={activityForm.evaluasiFasilitas}
                              onChange={(e) => setActivityForm({ ...activityForm, evaluasiFasilitas: e.target.value })}
                              className="w-full border border-amber-300 rounded-xl p-2.5 bg-white outline-none"
                            >
                              <option value="">Belum dievaluasi</option>
                              <option>Sangat Baik (95%)</option>
                              <option>Baik (92%)</option>
                              <option>Cukup (80%)</option>
                            </select>
                          </div>
                          <div>
                            <label className="font-bold text-amber-900 block mb-1" htmlFor="field-24">Dampak Nilai Karakter</label>
                            <select id="field-24" value={activityForm.evaluasiDampak}
                              onChange={(e) => setActivityForm({ ...activityForm, evaluasiDampak: e.target.value })}
                              className="w-full border border-amber-300 rounded-xl p-2.5 bg-white outline-none"
                            >
                              <option value="">Belum dievaluasi</option>
                              <option>Sangat Bermanfaat (97%)</option>
                              <option>Bermanfaat (85%)</option>
                              <option>Cukup (75%)</option>
                            </select>
                          </div>
                        </div>

                        <div>
                          <label className="font-bold text-amber-900 block mb-1" htmlFor="field-25">Catatan & Masukan Perbaikan Survey</label>
                          <input id="field-25" type="text"
                            placeholder="Ringkasan masukan mahasiswa dari evaluasi survey..."
                            value={activityForm.catatanSurvey}
                            onChange={(e) => setActivityForm({ ...activityForm, catatanSurvey: e.target.value })}
                            className="w-full border border-amber-300 rounded-xl p-2.5 bg-white outline-none"
                          />
                        </div>
                      </div>

                      {/* Baris 5: Ringkasan Laporan & Capaian Output Kegiatan (Persis Foto) */}
                      <div className="md:col-span-4">
                        <label className="font-bold text-slate-800 block mb-1" htmlFor="field-26">Ringkasan Laporan & Capaian Output Kegiatan</label>
                        <textarea id="field-26" rows="4"
                          placeholder="Tuliskan catatan capaian, evaluasi keberhasilan, dan dokumentasi output..."
                          value={activityForm.laporan}
                          onChange={(e) => setActivityForm({ ...activityForm, laporan: e.target.value })}
                          className="w-full border border-slate-300 rounded-2xl p-4 outline-none focus:border-[#D71920] text-sm"
                        ></textarea>
                      </div>

                    </div>

                    <div className="flex justify-end gap-3 pt-4 border-t">
                      <button
                        type="submit" disabled={busy}
                        className="px-8 py-3 bg-[#D71920] hover:bg-red-700 text-white font-bold rounded-xl shadow-lg transition-all text-xs tracking-wide"
                      >
                        Simpan & Publikasikan Kegiatan
                      </button>
                    </div>
                    </fieldset>
                  </form>}
                </div>

                {canWrite && editingId && <p className="text-xs text-slate-500">Peserta dan respons survei lama tetap dipakai bila Anda tidak mengimpor berkas pengganti.</p>}
                {/* TABEL KEGIATAN TERDATA */}
                <div role="region" aria-label="Daftar kegiatan tersimpan" className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden p-6 space-y-4">
                  <h3 className="font-bold text-sm text-slate-900">Daftar Kegiatan Terpublikasi ({filteredActivities.length})</h3>
                  <div className="flex gap-2"><button onClick={exportActivities} className="border rounded-lg px-3 py-2 text-xs">Ekspor Excel</button><button disabled={busy} onClick={()=>run(()=>downloadReportPdf({activities:filteredActivities,students:filteredStudents,surveys:filteredSurveys,filters:{year:filterYear,quarter:filterTw,category:filterCategory,search:searchNim},preparedBy:profileData.nama}))} className="border rounded-lg px-3 py-2 text-xs">Unduh PDF</button></div>
                  <p className="text-xs text-slate-500">PDF diunduh langsung dan memuat seluruh data sesuai filter laporan, tanpa formulir aplikasi.</p>
                  <label className="text-xs block">Tampilkan kegiatan<select aria-label="Jumlah kegiatan per halaman" value={activityPageSize} onChange={event=>{setActivityPageSize(event.target.value);setActivityPage(1);}} className="border rounded-lg p-2 ml-2"><option value="10">10</option><option value="50">50</option><option value="all">Semua (All)</option></select></label>
                  <div className="overflow-x-auto custom-scrollbar">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-[#991b1b] text-white uppercase text-[10px]">
                        <tr>
                          <th className="py-2.5 px-3">Tanggal</th>
                          <th className="py-2.5 px-3">Tahun</th>
                          <th className="py-2.5 px-3">TW</th>
                          <th className="py-2.5 px-3">Nama Kegiatan</th>
                          <th className="py-2.5 px-3">Peserta</th>
                          <th className="py-2.5 px-3">Skor Survey</th>
                          <th className="py-2.5 px-3">Narasumber</th>
                          <th className="py-2.5 px-3">Link Evident</th><th className="py-2.5 px-3">Aksi</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {filteredActivities.length===0 && <tr><td colSpan={9} className="p-6 text-center text-slate-400">Belum ada kegiatan yang sesuai filter.</td></tr>}
                        {pagedActivities.map((act) => (
                          <tr key={act.id} className="hover:bg-slate-50">
                            <td className="py-2.5 px-3 whitespace-nowrap">{act.tanggal}</td>
                            <td className="py-2.5 px-3">{act.tahun}</td>
                            <td className="py-2.5 px-3">{act.triwulan}</td>
                            <td className="py-2.5 px-3 font-bold text-slate-800">{act.namaKegiatan||'Belum diisi'}</td>
                            <td className="py-2.5 px-3">{act.jumlahPeserta??'—'} Mhs</td>
                            <td className="py-2.5 px-3 font-bold text-[#D71920]">★ {act.skorSurvey ?? "—"}</td>
                            <td className="py-2.5 px-3">{act.pembicara}</td>
                            <td className="py-2.5 px-3 text-blue-600 underline font-mono truncate max-w-xs">{/^https?:\/\//i.test(act.linkEvident)?<a href={act.linkEvident} target="_blank" rel="noopener noreferrer">{act.linkEvident}</a>:act.linkEvident}</td>
                            <td className="py-2.5 px-3 whitespace-nowrap">{canEdit(act)&&<><button disabled={busy} onClick={()=>editActivity(act)} className="text-blue-700 mr-3">Edit</button><button disabled={busy} onClick={()=>deleteActivity(act)} className="text-red-700">Hapus</button></>}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="flex flex-wrap justify-between items-center gap-3 text-xs text-slate-600"><p>Menampilkan {filteredActivities.length?activityStart+1:0}–{Math.min(activityStart+activityLimit,filteredActivities.length)} dari {filteredActivities.length} kegiatan. Ekspor tetap memuat semua hasil filter.</p><nav aria-label="Halaman daftar kegiatan" className="flex gap-3 items-center"><button disabled={currentActivityPage===1} onClick={()=>setActivityPage(currentActivityPage-1)} className="border rounded-lg p-2">Sebelumnya</button><span>Halaman {currentActivityPage} dari {activityPages}</span><button disabled={currentActivityPage===activityPages} onClick={()=>setActivityPage(currentActivityPage+1)} className="border rounded-lg p-2">Berikutnya</button></nav></div>
                </div>

              {!isOperator&&<SurveySummary surveys={filteredSurveys} activities={filteredActivities} />}
              <StudentRecap rows={filteredStudents} activities={filteredActivities} />
              </main>
            )}

            {/* ========================================================================= */}
            {/* 3. MENU: PENGATURAN ADMIN (BUATKAN & HAPUS AKUN)                           */}
            {/* ========================================================================= */}
            {activeNav === 'pengaturanAdmin' && canManageAccounts && (
              <main className="p-6 md:p-8 space-y-6 max-w-5xl mx-auto w-full">
                <div>
                  <h1 className="text-xl font-bold text-slate-900">Pengaturan Akun Administrator KKA</h1>
                  <p className="text-xs text-slate-500 mt-1">Kelola pembuatan akun baru, hak akses sistem, dan penghapusan admin terdaftar</p>
                </div>

                <div className="bg-white p-6 md:p-8 rounded-3xl border border-slate-200 shadow-sm space-y-4">
                  <h3 className="font-bold text-sm text-slate-900 border-b pb-2">Buatkan Akun Admin Baru</h3>
                  <form onSubmit={handleCreateAdmin} className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                    <div>
                      <label className="font-bold block mb-1" htmlFor="field-27">Username Admin *</label>
                      <input id="field-27" type="text"
                        required
                        placeholder="Contoh: admin_kemahasiswaan"
                        value={newAdmin.username}
                        onChange={(e) => setNewAdmin({ ...newAdmin, username: e.target.value })}
                        className="w-full border rounded-xl p-3 outline-none focus:border-[#D71920]"
                      />
                    </div>
                    <div>
                      <label className="font-bold block mb-1" htmlFor="field-28">Email Resmi Tel-U *</label>
                      <input id="field-28" type="email"
                        required
                        placeholder="nama@telkomuniversity.ac.id"
                        value={newAdmin.email}
                        onChange={(e) => setNewAdmin({ ...newAdmin, email: e.target.value })}
                        className="w-full border rounded-xl p-3 outline-none focus:border-[#D71920]"
                      />
                    </div>
                    <div>
                      <label className="font-bold block mb-1" htmlFor="field-29">Nama Lengkap Petugas *</label>
                      <input id="field-29" type="text"
                        required minLength={2} placeholder="Nama dan gelar petugas"
                        value={newAdmin.nama}
                        onChange={(e) => setNewAdmin({ ...newAdmin, nama: e.target.value })}
                        className="w-full border rounded-xl p-3 outline-none focus:border-[#D71920]"
                      />
                    </div>
                    <div>
                      <label className="font-bold block mb-1" htmlFor="field-30">Hak Akses / Role</label>
                      <select id="field-30" value={newAdmin.role}
                        onChange={(e) => setNewAdmin({ ...newAdmin, role: e.target.value })}
                        className="w-full border rounded-xl p-3 outline-none focus:border-[#D71920] bg-white font-semibold"
                      >
                        {isAdmin&&<><option value="admin">Super Admin KKA</option><option value="operator">Operator KKA</option><option value="verifier">Verifikator Survey</option></>}<option value="pengkar">Operator Pengkar</option><option value="asrama">Operator Asrama</option><option value="viewer">Viewer</option>
                      </select>
                    </div>
                    <div className="md:col-span-2"><label className="font-bold block mb-1" htmlFor="field-31">Password awal (minimal 12 karakter) *</label><input id="field-31" required minLength={12} type="password" autoComplete="new-password" value={newAdmin.password} onChange={e=>setNewAdmin({...newAdmin,password:e.target.value})} className="w-full border rounded-xl p-3" /></div>
                    <div className="md:col-span-2 flex justify-end pt-2">
                      <button type="submit" disabled={busy} className="px-6 py-2.5 bg-[#D71920] hover:bg-red-700 text-white font-bold rounded-xl shadow-md text-xs">
                        + Buatkan Akun Admin
                      </button>
                    </div>
                  </form>
                </div>

                <div className="bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden p-6 space-y-4">
                  <h3 className="font-bold text-sm text-slate-900">Daftar Administrator Aktif ({adminList.filter(a=>a.status==='Aktif').length})</h3>
                  <div className="overflow-x-auto custom-scrollbar">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-[#1e293b] text-white uppercase text-[10px]">
                        <tr>
                          <th className="py-2.5 px-4">Nama Petugas</th>
                          <th className="py-2.5 px-4">Username</th>
                          <th className="py-2.5 px-4">Email Institusi</th>
                          <th className="py-2.5 px-4">Role</th>
                          <th className="py-2.5 px-4">Status</th>
                          <th className="py-2.5 px-4 text-center">Aksi</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {adminList.map((adm) => (
                          <tr key={adm.id} className="hover:bg-slate-50">
                            <td className="py-3 px-4 font-bold text-slate-800">{adm.nama}</td>
                            <td className="py-3 px-4 font-mono">{adm.username}</td>
                            <td className="py-3 px-4 text-slate-600">{adm.email}</td>
                            <td className="py-3 px-4"><span className="px-2 py-0.5 rounded bg-blue-100 text-blue-800 font-bold text-[10px]">{roleLabel(adm.role)}</span></td>
                            <td className="py-3 px-4"><span className={`px-2 py-0.5 rounded font-bold text-[10px] ${adm.status==='Aktif'?'bg-emerald-100 text-emerald-800':'bg-slate-100 text-slate-500'}`}>{adm.status}</span></td>
                            <td className="py-3 px-4 text-center">
                              <button
                                disabled={busy || adm.status!=="Aktif" || adm.username===profileData.username} onClick={() => handleDeleteAdmin(adm.id, adm.username)}
                                className="px-3 py-1 bg-red-50 hover:bg-red-100 text-[#D71920] font-bold rounded-lg transition-all"
                              >
                                Nonaktifkan
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </main>
            )}

            {/* ========================================================================= */}
            {/* 4. MENU: PENGATURAN (PROFILE & LOGOUT)                                     */}
            {/* ========================================================================= */}
            {activeNav === 'pengaturan' && (
              <main className="p-6 md:p-8 space-y-6 max-w-4xl mx-auto w-full">
                <div>
                  <h1 className="text-xl font-bold text-slate-900">Pengaturan Profile & Keamanan Akun</h1>
                  <p className="text-xs text-slate-500 mt-1">Kelola data profil Administrator KKA dan sesi akses sistem</p>
                </div>

                <div className="bg-white p-6 md:p-8 rounded-3xl border border-slate-200 shadow-sm space-y-6">
                  <div className="flex items-center gap-4 border-b pb-6">
                    <div className="w-16 h-16 rounded-2xl bg-[#1e293b] text-white flex items-center justify-center text-xl font-black shadow-md">
                      {profileData.nama.slice(0,2).toUpperCase()}
                    </div>
                    <div>
                      <h2 className="text-lg font-bold text-slate-900">{profileData.nama}</h2>
                      <p className="text-xs text-slate-500">{roleLabel(profileData.role)} • {profileData.kampus}</p>
                      <span className="inline-block mt-1 px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-bold text-[10px]">Sesi Terautentikasi Server</span>
                    </div>
                  </div>

                  <form onSubmit={saveProfile} className="space-y-4 text-xs">
                    <div><label className="font-bold block mb-1" htmlFor="field-32">Username login</label><input id="field-32" required minLength={3} value={profileData.username} onChange={e=>setProfileData({...profileData,username:e.target.value})} className="w-full border rounded-xl p-3" /><p className="text-slate-500 mt-1">Gunakan username ini saat login berikutnya.</p></div>
                    <div><label className="font-bold block mb-1" htmlFor="field-33">Email</label><input id="field-33" type="email" value={profileData.email} onChange={e=>setProfileData({...profileData,email:e.target.value})} className="w-full border rounded-xl p-3" /></div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="font-bold block mb-1" htmlFor="field-34">Nama Petugas</label>
                        <input id="field-34" type="text"
                          value={profileData.nama}
                          onChange={(e) => setProfileData({ ...profileData, nama: e.target.value })}
                          className="w-full border rounded-xl p-3 outline-none focus:border-[#D71920]"
                        />
                      </div>
                      <div>
                        <label className="font-bold block mb-1" htmlFor="field-35">Peran / Jabatan</label>
                        <input id="field-35" type="text"
                          readOnly
                          value={roleLabel(profileData.role)}
                          className="w-full border rounded-xl p-3 bg-slate-50 text-slate-500"
                        />
                      </div>
                      <div className="md:col-span-2">
                        <label className="font-bold block mb-1" htmlFor="field-36">Instansi / Unit Kerja</label>
                        <input id="field-36" type="text"
                          value={profileData.instansi}
                          onChange={(e) => setProfileData({ ...profileData, instansi: e.target.value })}
                          className="w-full border rounded-xl p-3 outline-none focus:border-[#D71920]"
                        />
                      </div>
                    </div>

                    <div className="flex justify-between items-center pt-4 border-t">
                      <button
                        type="button"
                        onClick={handleLogout}
                        className="px-5 py-2.5 bg-red-50 hover:bg-red-100 text-[#D71920] font-bold rounded-xl text-xs transition-all"
                      >
                        Log Out dari Aplikasi
                      </button>

                      <button
                        type="submit" disabled={busy}
                        className="px-6 py-2.5 bg-[#D71920] hover:bg-red-700 text-white font-bold rounded-xl text-xs shadow-md transition-all"
                      >
                        Simpan Perubahan Profil
                      </button>
                    </div>
                  </form>
                </div>
              </main>
            )}

            {activeNav==='pengaturan' && <section className="mx-auto mb-8 px-8 w-full max-w-4xl"><form onSubmit={changePassword} className="bg-white p-6 border rounded-3xl space-y-4 text-xs"><h3 className="font-bold text-base">Ganti Password</h3><p className="text-slate-500">Setelah menyimpan, semua sesi akun ini keluar. Login kembali memakai password baru.</p>{[['current_password','Password saat ini'],['new_password','Password baru (minimal 12 karakter)'],['confirm','Ulangi password baru']].map(([key,label])=><label key={key} className="block font-bold">{label}<input required type="password" minLength={key==='current_password'?1:12} autoComplete={key==='current_password'?'current-password':'new-password'} value={passwordForm[key]} onChange={e=>setPasswordForm({...passwordForm,[key]:e.target.value})} className="block w-full border rounded-xl p-3 mt-1" /></label>)}<button disabled={busy} className="bg-[#D71920] text-white px-5 py-3 rounded-xl font-bold">Simpan Password Baru</button></form></section>}
            {/* FOOTER RESMI DIT. KKA TELKOM UNIVERSITY */}
            <footer className="mt-auto py-4 bg-white border-t border-slate-200 text-center text-xs text-slate-500 space-y-1">
              <div className="font-bold text-slate-700">
                Direktorat Kemahasiswaan, Pengembangan Karier dan Alumni
              </div>
              <div className="text-[10px] text-slate-400">
                Telkom University • Sistem Monitoring Laporan Karakter & Hasil Evaluasi Survey Mahasiswa
              </div>
            </footer>

          </div>
        </div>
      );
    }

    const root = createRoot(document.getElementById('root'));
    root.render(<App />);
