<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.10.2-A Coruña" hasScaleBasedVisibilityFlag="0" maxScale="0" styleCategories="AllStyleCategories" minScale="1e+08">
  <flags>
    <Identifiable>1</Identifiable>
    <Removable>1</Removable>
    <Searchable>1</Searchable>
  </flags>
  <customproperties>
    <property value="false" key="WMSBackgroundLayer"/>
    <property value="false" key="WMSPublishDataSourceUrl"/>
    <property value="0" key="embeddedWidgets/count"/>
    <property value="Value" key="identify/format"/>
  </customproperties>
  <pipe>
    <rasterrenderer classificationMax="5" type="singlebandpseudocolor" alphaBand="-1" classificationMin="0.545" opacity="1" band="1">
      <rasterTransparency/>
      <minMaxOrigin>
        <limits>None</limits>
        <extent>WholeRaster</extent>
        <statAccuracy>Estimated</statAccuracy>
        <cumulativeCutLower>0.02</cumulativeCutLower>
        <cumulativeCutUpper>0.98</cumulativeCutUpper>
        <stdDevFactor>2</stdDevFactor>
      </minMaxOrigin>
      <rastershader>
        <colorrampshader colorRampType="DISCRETE" classificationMode="1" clip="0">
          <colorramp type="gradient" name="[source]">
            <prop v="255,255,255,255" k="color1"/>
            <prop v="243,245,117,255" k="color2"/>
            <prop v="1" k="discrete"/>
            <prop v="gradient" k="rampType"/>
            <prop v="0.177885;196,199,197,255:0.378606;245,212,230,255:0.502404;252,187,228,255:0.632212;240,161,201,255:0.765625;207,41,146,255:0.866587;245,117,147,255:0.955529;243,245,117,255:0.956731;243,245,117,255" k="stops"/>
          </colorramp>
          <item value="0.545" alpha="255" color="#ffffff" label="&lt;= 0.5"/>
          <item value="0.75" alpha="255" color="#f7d7ec" label="0.55-0.75"/>
          <item value="1" alpha="255" color="#f0bdd9" label="0.75-1.0"/>
          <item value="1.3" alpha="255" color="#f09ed2" label="1.0-1.3"/>
          <item value="2" alpha="255" color="#e775b0" label="1.3-2.0"/>
          <item value="3" alpha="255" color="#cf2992" label="2.0-3.0"/>
          <item value="4" alpha="255" color="#f57593" label="3.0-4.0"/>
          <item value="5" alpha="255" color="#f3f575" label="4.0-5.0"/>
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
    <brightnesscontrast brightness="0" contrast="0"/>
    <huesaturation colorizeBlue="128" colorizeGreen="128" colorizeRed="255" grayscaleMode="0" saturation="0" colorizeStrength="100" colorizeOn="0"/>
    <rasterresampler maxOversampling="2"/>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
