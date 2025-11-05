<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis styleCategories="AllStyleCategories" minScale="1e+08" maxScale="0" hasScaleBasedVisibilityFlag="0" version="3.22.16-Białowieża">
  <flags>
    <Identifiable>1</Identifiable>
    <Removable>1</Removable>
    <Searchable>1</Searchable>
    <Private>0</Private>
  </flags>
  <temporal mode="0" fetchMode="0" enabled="0">
    <fixedRange>
      <start></start>
      <end></end>
    </fixedRange>
  </temporal>
  <customproperties>
    <Option type="Map">
      <Option value="false" type="bool" name="WMSBackgroundLayer"/>
      <Option value="false" type="bool" name="WMSPublishDataSourceUrl"/>
      <Option value="0" type="int" name="embeddedWidgets/count"/>
      <Option value="Value" type="QString" name="identify/format"/>
    </Option>
  </customproperties>
  <pipe-data-defined-properties>
    <Option type="Map">
      <Option value="" type="QString" name="name"/>
      <Option name="properties"/>
      <Option value="collection" type="QString" name="type"/>
    </Option>
  </pipe-data-defined-properties>
  <pipe>
    <provider>
      <resampling zoomedInResamplingMethod="nearestNeighbour" maxOversampling="2" zoomedOutResamplingMethod="nearestNeighbour" enabled="false"/>
    </provider>
    <rasterrenderer nodataColor="" band="1" type="singlebandpseudocolor" classificationMax="0.628387426970788" opacity="1" alphaBand="-1" classificationMin="0">
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
        <colorrampshader maximumValue="0.62838742697078831" colorRampType="INTERPOLATED" clip="0" minimumValue="0" classificationMode="3" labelPrecision="4">
          <colorramp type="gradient" name="[source]">
            <Option type="Map">
              <Option value="230,230,230,255" type="QString" name="color1"/>
              <Option value="239,227,0,255" type="QString" name="color2"/>
              <Option value="0" type="QString" name="discrete"/>
              <Option value="gradient" type="QString" name="rampType"/>
              <Option value="0.250005;41,115,190,255:0.50001;24,189,117,255:0.750015;35,224,60,255" type="QString" name="stops"/>
            </Option>
            <prop k="color1" v="230,230,230,255"/>
            <prop k="color2" v="239,227,0,255"/>
            <prop k="discrete" v="0"/>
            <prop k="rampType" v="gradient"/>
            <prop k="stops" v="0.250005;41,115,190,255:0.50001;24,189,117,255:0.750015;35,224,60,255"/>
          </colorramp>
          <item label="0,00" color="#e6e6e6" value="0" alpha="255"/>
          <item label="0,16" color="#2973be" value="0.1571" alpha="255"/>
          <item label="0,31" color="#18bd75" value="0.3142" alpha="255"/>
          <item label="0,47" color="#23e03c" value="0.4713" alpha="255"/>
          <item label="0,63" color="#efe300" value="0.628387426970788" alpha="255"/>
          <rampLegendSettings minimumLabel="" direction="0" useContinuousLegend="0" maximumLabel="" prefix="" suffix="" orientation="2">
            <numericFormat id="basic">
              <Option type="Map">
                <Option value="" type="QChar" name="decimal_separator"/>
                <Option value="6" type="int" name="decimals"/>
                <Option value="0" type="int" name="rounding_type"/>
                <Option value="false" type="bool" name="show_plus"/>
                <Option value="true" type="bool" name="show_thousand_separator"/>
                <Option value="false" type="bool" name="show_trailing_zeros"/>
                <Option value="" type="QChar" name="thousand_separator"/>
              </Option>
            </numericFormat>
          </rampLegendSettings>
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
    <brightnesscontrast contrast="0" gamma="1" brightness="0"/>
    <huesaturation colorizeBlue="128" colorizeStrength="100" saturation="0" colorizeGreen="128" colorizeOn="0" grayscaleMode="0" invertColors="0" colorizeRed="255"/>
    <rasterresampler maxOversampling="2"/>
    <resamplingStage>resamplingFilter</resamplingStage>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
