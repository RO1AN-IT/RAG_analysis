<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.10.2-A Coruña" minScale="1e+08" hasScaleBasedVisibilityFlag="0" styleCategories="AllStyleCategories" maxScale="0">
  <flags>
    <Identifiable>1</Identifiable>
    <Removable>1</Removable>
    <Searchable>1</Searchable>
  </flags>
  <customproperties>
    <property key="WMSBackgroundLayer" value="false"/>
    <property key="WMSPublishDataSourceUrl" value="false"/>
    <property key="embeddedWidgets/count" value="0"/>
    <property key="identify/format" value="Value"/>
  </customproperties>
  <pipe>
    <rasterrenderer opacity="1" classificationMin="0" alphaBand="-1" type="singlebandpseudocolor" band="1" classificationMax="100">
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
        <colorrampshader clip="0" classificationMode="2" colorRampType="INTERPOLATED">
          <colorramp type="gradient" name="[source]">
            <prop v="64,64,255,255" k="color1"/>
            <prop v="255,64,64,255" k="color2"/>
            <prop v="1" k="discrete"/>
            <prop v="gradient" k="rampType"/>
            <prop v="0.0877404;64,234,234,255:0.454545;96,255,96,255:0.636364;234,234,64,255:0.728365;255,64,64,255" k="stops"/>
          </colorramp>
          <item label="0" value="0" color="#4040ff" alpha="255"/>
          <item label="25" value="25" color="#40eaea" alpha="255"/>
          <item label="50" value="50" color="#60ff60" alpha="255"/>
          <item label="75" value="75" color="#ffc640" alpha="255"/>
          <item label="100" value="100" color="#ff4040" alpha="255"/>
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
    <brightnesscontrast brightness="0" contrast="0"/>
    <huesaturation colorizeOn="0" colorizeRed="255" saturation="0" colorizeStrength="100" grayscaleMode="0" colorizeGreen="128" colorizeBlue="128"/>
    <rasterresampler maxOversampling="2"/>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
