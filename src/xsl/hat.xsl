<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="html" />
<xsl:template match="/">
	
<head>  
    <title>SAlomeTools log</title>
    <style type="text/css">
        table       { 
                      margin:1px;
                      padding:1px;
                      border-collapse:collapse;
                      empty-cells : show;
                    }
        td          { vertical-align : center;}
        h1          { text-align : center; }
        .legend     { font-weight : bold;
                      text-align : center;
                    } 
        .def        { font-family: Arial, Verdana, "Times New Roman", Times, serif;}
        hr.note     { color: #BFBFBF; }
        .note       { text-align : right; font-style: italic; font-size: small; }
        div.release { -moz-column-count: 2;
                      overflow: auto;
                      max-height: 250px;
                    }
    </style>
</head>
	<body class="def" bgcolor="aliceblue">
		<h1><img src="LOGO-SAT.png"/></h1>
			<table border="0">
				<tr>
				<td width="100px">Command</td><td width="100px">date</td><td>time</td>
				</tr>
				<xsl:for-each select="LOGlist/LogCommand">
					<xsl:sort select="." order="descending" />
					<tr bgcolor="aliceblue" width="2">
						<td>
							<a title="log" target="_blank">
								<xsl:attribute name="href"><xsl:value-of select="."/></xsl:attribute>
								<xsl:value-of select="@cmd"/>
							</a>
						</td>
						<td><xsl:value-of select="@date"/></td>
						<td><xsl:value-of select="@hour"/></td>
					</tr>
				</xsl:for-each>
			</table>
	</body>
</xsl:template>
</xsl:stylesheet>
