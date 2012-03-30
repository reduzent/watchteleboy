==============================================
How to record from tvbrowser with watchteleboy
==============================================


What is TV-Browser?
-------------------

TV-Browser is a free electronic program guide (EPG) with a nice
plugin architecture. If configured accordingly, you can
schedule recordings with a simple mouse click and watchteleboy
will record the show for you.


Where can I get it?
-------------------

You can download the TV-Browser appliaction from here:
http://www.tvbrowser.org/downloads-mainmenu-5/tv-browser-mainmenu-6.html


How to integrate watchteleboy in TV-Browser?
--------------------------------------------

o Install the 'Recording control' Plugin
  Launch the TV-Browser Application, open the menu 'Tools' -> 
  'Manage Plugins' and click on the <Update/install plugins>
  button. 
  Set the checkbox at 'Recording control' and click <OK>.
  You might need to restart TV-Browser to enable the new plugin.

o Configure the watchteleboy device
  Open the menu 'Tools' -> 'Recording control'
  Switch to the 'Devices' tab and
  click 'Import Device'.
  Select the file 'watchteleboy-recorder.tcf' and click <OK>
 
That's it. You're done!


How to use it?
--------------

In TV-Browser you can now simply right-click a show that you would like
to schedule for recording and choose 'Record'. TV-Browser might be 
blocked for a few seconds, until watchteleboy is finished.

You can check the result with the command 'crontab -l'.
  
  
