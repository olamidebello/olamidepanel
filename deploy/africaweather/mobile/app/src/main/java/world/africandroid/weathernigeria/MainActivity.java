package world.africandroid.africaweather;
import android.app.Activity;
import android.os.Bundle;
import android.webkit.*;
import android.content.Intent;
import android.net.Uri;
import android.content.SharedPreferences;
import android.widget.*;
import android.view.View;
import org.json.*;
import java.io.*;
import java.util.*;
public class MainActivity extends Activity {
    private WebView web;
    private Spinner selector;
    private SharedPreferences preferences;
    private final List<String> domains = new ArrayList<>();
    private final List<String> names = new ArrayList<>();
    private static final String HOST = "africaweather.africandroid.world";
    private boolean syncing = false;
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        preferences = getSharedPreferences("weather", MODE_PRIVATE);
        names.add("All Africa"); domains.add(HOST);
        try {
            InputStream stream=getAssets().open("countries.json");
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();
            byte[] buffer=new byte[4096];int count;
            while((count=stream.read(buffer))!=-1)bytes.write(buffer,0,count);
            stream.close();JSONArray countries=new JSONArray(bytes.toString("UTF-8"));
            for(int i=0;i<countries.length();i++) { JSONObject country=countries.getJSONObject(i);names.add(country.getString("name"));domains.add(country.getString("domain")); }
        } catch(Exception ignored) { Toast.makeText(this,"Country list unavailable. Use the Africa directory.",Toast.LENGTH_LONG).show(); }
        LinearLayout layout=new LinearLayout(this);layout.setOrientation(LinearLayout.VERTICAL);
        selector=new Spinner(this);selector.setContentDescription("Preferred country");
        ArrayAdapter<String> adapter=new ArrayAdapter<>(this,android.R.layout.simple_spinner_item,names);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);selector.setAdapter(adapter);
        layout.addView(selector,new LinearLayout.LayoutParams(-1,-2));
        web=new WebView(this);layout.addView(web,new LinearLayout.LayoutParams(-1,0,1));setContentView(layout);
        web.getSettings().setJavaScriptEnabled(true);
        web.getSettings().setDomStorageEnabled(true);
        web.getSettings().setAllowFileAccess(false);
        web.getSettings().setAllowContentAccess(false);
        web.getSettings().setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        int saved=domains.indexOf(preferences.getString("country",HOST));if(saved<0)saved=0;
        selector.setSelection(saved);
        selector.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener(){
            @Override public void onItemSelected(AdapterView<?> parent,View view,int position,long id){
                if(syncing)return;String domain=domains.get(position);
                preferences.edit().putString("country",domain).apply();
                String current=web.getUrl();
                if(current==null||!domain.equals(Uri.parse(current).getHost()))web.loadUrl("https://"+domain+"/");
            }
            @Override public void onNothingSelected(AdapterView<?> parent){}
        });
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){
                Uri uri=request.getUrl();
                if("https".equals(uri.getScheme())&&domains.contains(uri.getHost()))return false;
                if("https".equals(uri.getScheme()))try{startActivity(new Intent(Intent.ACTION_VIEW,uri));}catch(android.content.ActivityNotFoundException ignored){}
                return true;
            }
            @Override public void onPageFinished(WebView view,String url){
                int position=domains.indexOf(Uri.parse(url).getHost());
                if(position>=0){syncing=true;selector.setSelection(position);syncing=false;preferences.edit().putString("country",domains.get(position)).apply();}
            }
        });
        web.setDownloadListener((url,userAgent,contentDisposition,mimeType,contentLength)->{
            if("https".equals(Uri.parse(url).getScheme()))try{startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(url)));}catch(android.content.ActivityNotFoundException ignored){}
        });
        if(state==null)web.loadUrl("https://"+domains.get(saved)+"/");else if(web.restoreState(state)==null)web.loadUrl("https://"+domains.get(saved)+"/");
    }
    @Override protected void onSaveInstanceState(Bundle state){web.saveState(state);super.onSaveInstanceState(state);}
    @Override public void onBackPressed(){if(web.canGoBack())web.goBack();else super.onBackPressed();}
    @Override protected void onDestroy(){web.destroy();super.onDestroy();}
}
