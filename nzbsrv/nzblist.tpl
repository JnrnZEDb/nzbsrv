<html>
	<head>
		<meta name="viewport" content="width=device-width, initial-scale=1.0">
		<title>nzbsrv</title>
		<style>
			.dlbutton, .dlbuttongreyed { background:#3DBF9A; color:#FFF; cursor:pointer; border-radius:5px; border:none; padding: 3px 10px; margin-top: 10px; display: inline-block; }
			.dlbuttongreyed { opacity:0.35; cursor:default; }
		</style>
		<script type="text/javascript">
			function download(element) {
				element.className = 'dlbuttongreyed';
				element.disabled = true;
				var xhr= new XMLHttpRequest();
				xhr.open('GET', element.getAttribute('nzburl'), true);
				xhr.send();
			}
			function ignoretitle(element) {
				var xhr= new XMLHttpRequest();
				xhr.open('GET', '/ignore/' + element.getAttribute('nzbtitle'), true);
				xhr.send();
				element.parentNode.outerHTML = "";
				delete element.parentNode;
			}
		</script>
	</head>
	<body style="margin:0; font-family:Helvetica Neue,Helvetica,Arial,sans-serif;">
		<table style="vertical-align:middle; max-width:100%; width:100%; margin-bottom:20px; border-spacing:2px; border-color:gray; font-size:small; border-collapse: collapse;">
			{{content}}
		</table>
	</body>
</html>