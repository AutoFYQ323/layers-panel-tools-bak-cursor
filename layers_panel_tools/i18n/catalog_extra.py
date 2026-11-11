# -*- coding: utf-8 -*-
"""Sentences added after the 1.0.3 catalog.

Keys must match a tr() literal exactly, including newlines. This folder is
skipped by the Chinese-literal scan, so the keys live here on purpose.
"""


def _rows():
    rows = []

    def add(zh, en, es, fr, ar):
        rows.append((zh, en, es, fr, ar))

    add(
        "勾选多个矢量图层，选文件夹与格式，按图层名各导出一份。导出完成后会说明写到了哪里。勾选「合并为一个文件」时改为选择一个保存路径：GeoPackage、SQLite、KML、GML 一个文件多层；KMZ 写成一个 .kmz；Excel 和 ODS 一个工作簿一层一个表；CSV 再多一个「并成同一个表」，默认不勾，这时因为 CSV 不能有多个工作表，会写成同名的 Excel 文件，每个图层一个表，表名是图层名；勾上之后并进同一个 CSV 表，同名字段只出现一次，每个图层的字段都会保留，并加一列记下原来的图层名；DXF 也会合成一个文件，但会丢掉大部分属性。",
        "Check vector layers, pick a folder and a format, and export one file per layer name. When it finishes, a dialog says where the files went. When “Merge into one file” is checked, you choose one save path instead: GeoPackage, SQLite, KML, and GML keep one layer each inside that file; KMZ is written as one .kmz; Excel and ODS use one sheet per layer. CSV adds “One table”, off by default: CSV cannot hold several sheets, so the same name is written as an Excel file, one sheet per layer, named after the layer. When that box is on, every feature goes into one CSV table; a field name shared by several layers appears once, every layer’s own fields are kept, and a column records the source layer name. DXF is also combined into one file, but most attributes are dropped.",
        "Marca capas vectoriales, elige carpeta y formato, y exporta un archivo por nombre de capa. Al terminar, un cuadro dice dónde quedaron. Si marcas «Unir en un archivo», eliges una ruta de guardado: GeoPackage, SQLite, KML y GML guardan una capa cada una dentro de ese archivo; KMZ se escribe como un .kmz; Excel y ODS usan una hoja por capa. CSV añade «Una sola tabla», desmarcada por defecto: CSV no puede tener varias hojas, así que se escribe un Excel con el mismo nombre, una hoja por capa y con el nombre de la capa. Si se marca, todas las entidades van a una tabla CSV; un campo con el mismo nombre aparece una sola vez, no falta ningún campo de ninguna capa, y una columna guarda el nombre de la capa de origen. DXF también se junta en un solo archivo, pero pierde la mayoría de los atributos.",
        "Cochez des couches vectorielles, choisissez un dossier et un format, et exportez un fichier par nom de couche. À la fin, une boîte indique où les fichiers ont été écrits. Si « Fusionner en un fichier » est coché, vous choisissez un chemin d’enregistrement : GeoPackage, SQLite, KML et GML gardent une couche chacun dans ce fichier ; le KMZ est écrit en un .kmz ; Excel et ODS utilisent une feuille par couche. Le CSV ajoute « Une seule table », décochée par défaut : un CSV ne peut pas avoir plusieurs feuilles, donc le même nom est écrit en Excel, une feuille par couche, nommée comme la couche. Si la case est cochée, toutes les entités vont dans une table CSV ; un nom de champ commun n’apparaît qu’une fois, aucun champ d’aucune couche n’est perdu, et une colonne retient le nom de la couche d’origine. Le DXF est aussi regroupé en un seul fichier, mais la plupart des attributs sont perdus.",
        "حدد طبقات متجهة واختر مجلدًا وتنسيقًا، ويُصدَّر ملف لكل اسم طبقة. عند الانتهاء تظهر رسالة بمكان الملفات. عند تحديد «دمج في ملف واحد» تختار مسار الحفظ: GeoPackage وSQLite وKML وGML يحتفظ كل منها بطبقة داخل ذلك الملف؛ ويُكتب KMZ كملف ‎.kmz واحد؛ وExcel وODS يستخدمان ورقة لكل طبقة. يضيف CSV خيار «جدول واحد»، وهو غير محدد افتراضيًا: CSV لا يحتمل عدة أوراق، فيُكتب ملف Excel بالاسم نفسه، ورقة لكل طبقة باسم الطبقة. عند تحديده تذهب كل المعالم إلى جدول CSV واحد؛ اسم الحقل المشترك يظهر مرة واحدة، ولا يُسقط أي حقل من أي طبقة، ويُضاف عمود باسم الطبقة الأصلية. ويُجمع DXF أيضًا في ملف واحد، لكن معظم السمات تُسقط.",
    )
    add(
        "五项都作用在当前工程。清空数据会删除全部矢量图层的全部要素，图层还在，删掉后不能恢复。打开编辑、保存关闭针对所有矢量图层，做成了不弹框，失败才说明。复制到空、复制图层只针对当前选中的那一个图层，样式跟着走。复制到空不含要素，复制图层连要素一起复制。复制前会说明图层、路径和原格式。清空和复制做成了也会弹出。",
        "All five actions work on the current project. Clear data deletes every feature in every vector layer. The layers stay, and the deletion cannot be undone. Start editing and Save and close apply to every vector layer; success stays quiet, and only a failure is reported. Copy empty and Copy layer apply only to the one selected layer, and the style comes along. Copy empty has no features. Copy layer copies the features too. Before copying, the dialog names the layer, the path, and the original format. Clear data and the two copy actions still report when they succeed.",
        "Las cinco acciones actúan sobre el proyecto actual. Vaciar datos borra todas las entidades de todas las capas vectoriales. Las capas siguen ahí y lo borrado no se puede recuperar. Abrir edición y Guardar y cerrar valen para todas las capas vectoriales; si salen bien no avisan, y solo avisan si fallan. Copiar vacío y Copiar capa solo afectan a la capa seleccionada, y el estilo las acompaña. Copiar vacío no incluye entidades. Copiar capa copia también las entidades. Antes de copiar se indican la capa, la ruta y el formato original. Vaciar datos y las dos copias sí avisan cuando terminan.",
        "Les cinq actions portent sur le projet en cours. Vider les données supprime toutes les entités de toutes les couches vectorielles. Les couches restent, et la suppression est irréversible. Ouvrir l’édition et Enregistrer et fermer s’appliquent à toutes les couches vectorielles ; une réussite reste silencieuse, seul un échec est signalé. Copier à vide et Copier la couche ne visent que la couche sélectionnée, et le style suit. Copier à vide n’a pas d’entités. Copier la couche copie aussi les entités. Avant la copie, la boîte indique la couche, le chemin et le format d’origine. Vider les données et les deux copies signalent aussi leur réussite.",
        "الإجراءات الخمسة تعمل على المشروع الحالي. مسح البيانات يحذف كل المعالم في كل الطبقات المتجهة. الطبقات تبقى، والحذف لا يُسترجع. فتح التحرير وحفظ وإغلاق يشملان كل الطبقات المتجهة؛ النجاح بلا رسالة، والفشل فقط يُبلَّغ. النسخ فارغًا ونسخ الطبقة يقتصران على الطبقة المحددة، والنمط يتبعها. النسخ فارغًا بلا معالم. نسخ الطبقة ينسخ المعالم أيضًا. قبل النسخ تُذكر الطبقة والمسار والتنسيق الأصلي. مسح البيانات وعمليتا النسخ تظهر نتيجتهما عند النجاح أيضًا.",
    )
    add(
        "在当前选中的线两端标出起点和终点，并显示长度（米）。不写入图层，也不换掉选线工具。小窗可以拖动。开/关控制标注。展开后列出所选线，取消勾选会同时取消 QGIS 里的选中。最多标前 80 条。关掉小窗即停止。",
        "Mark the start and end of each selected line and show the length in meters. Nothing is written to the layer, and the line-selection tool stays as it is. The small window can be dragged. On/off controls the marks. When expanded, it lists the selected lines; clearing a check also clears that feature in QGIS. At most the first 80 lines are marked. Closing the window stops it.",
        "Marca el inicio y el final de cada línea seleccionada y muestra la longitud en metros. No escribe en la capa ni cambia la herramienta de selección de líneas. La ventanita se puede arrastrar. Activar/desactivar controla las marcas. Al desplegar, lista las líneas elegidas; quitar la casilla también quita la selección en QGIS. Como máximo se marcan las 80 primeras. Cerrar la ventana lo detiene.",
        "Marquez le début et la fin de chaque ligne sélectionnée et affichez la longueur en mètres. Rien n’est écrit dans la couche, et l’outil de sélection de lignes reste en place. La petite fenêtre se déplace. Marche/arrêt commande les marques. Une fois dépliée, elle liste les lignes choisies ; décocher retire aussi la sélection dans QGIS. Au plus les 80 premières lignes sont marquées. Fermer la fenêtre arrête tout.",
        "يضع علامة على بداية ونهاية كل خط محدد ويعرض الطول بالأمتار. لا يكتب في الطبقة ولا يستبدل أداة تحديد الخطوط. النافذة الصغيرة تُسحب. تشغيل/إيقاف يتحكم بالعلامات. عند الفتح تُسرد الخطوط المختارة، وإلغاء التحديد يلغي التحديد في QGIS أيضًا. يُعلَّم أول 80 خطًا على الأكثر. إغلاق النافذة يوقفه.",
    )
    add(
        "选择一个图层，按类写成多个文件，默认存到工程所在文件夹，格式默认是 ESRI 形状文件。分类图层默认按图例里的分类、分级或规则；普通图层默认按字段，每个不同的值一个文件。下拉框里分类图层用粗体红色标出，并显示要素个数。超过上限会跳过并说明。",
        "Choose one layer and write one file per class, by default into the project folder, in ESRI Shapefile. A classified layer starts from its categories, ranges, or rules. An ordinary layer starts from a field, one file per distinct value. Classified layers are shown in bold red in the list, with the feature count. Above the limit, the export stops and says why.",
        "Elige una capa y escribe un archivo por clase, por defecto en la carpeta del proyecto y en ESRI Shapefile. Una capa clasificada empieza por sus categorías, intervalos o reglas. Una capa normal empieza por un campo, un archivo por valor distinto. Las capas clasificadas salen en negrita roja en la lista, con el número de entidades. Por encima del tope, la exportación se detiene y explica por qué.",
        "Choisissez une couche et écrivez un fichier par classe, par défaut dans le dossier du projet, au format ESRI Shapefile. Une couche classée part de ses catégories, paliers ou règles. Une couche ordinaire part d’un champ, un fichier par valeur distincte. Les couches classées apparaissent en gras rouge dans la liste, avec le nombre d’entités. Au-dessus du plafond, l’export s’arrête et dit pourquoi.",
        "اختر طبقة واحدة واكتب ملفًا لكل فئة، افتراضيًا في مجلد المشروع وبتنسيق ESRI Shapefile. الطبقة المصنفة تبدأ من فئاتها أو نطاقاتها أو قواعدها. الطبقة العادية تبدأ من حقل، ملف لكل قيمة مختلفة. الطبقات المصنفة تظهر بالأحمر العريض في القائمة، مع عدد المعالم. إذا تجاوز العدد الحد يتوقف التصدير ويذكر السبب.",
    )
    add("分类导出", "Export by class", "Exportar por clase", "Exporter par classe", "تصدير حسب الفئة")
    add(
        "按图例分类或按字段，把一个图层拆成多个文件",
        "Split one layer into several files by legend class or by field",
        "Parte una capa en varios archivos por clase de leyenda o por campo",
        "Découpe une couche en plusieurs fichiers par classe de légende ou par champ",
        "يقسم طبقة واحدة إلى عدة ملفات حسب فئة المفتاح أو حسب الحقل",
    )
    add(
        "选择一个图层。分类图层默认按图例，普通图层默认按字段。每一类或每个不同的值写成一个文件。",
        "Choose one layer. A classified layer starts on the legend; an ordinary layer starts on a field. Each class, or each distinct value, becomes one file.",
        "Elige una capa. Una capa clasificada empieza por la leyenda; una capa normal empieza por un campo. Cada clase, o cada valor distinto, es un archivo.",
        "Choisissez une couche. Une couche classée commence par la légende ; une couche ordinaire commence par un champ. Chaque classe, ou chaque valeur distincte, devient un fichier.",
        "اختر طبقة واحدة. الطبقة المصنفة تبدأ من المفتاح، والطبقة العادية تبدأ من حقل. كل فئة، أو كل قيمة مختلفة، تصبح ملفًا.",
    )
    add("按图例分类", "By legend", "Por leyenda", "Par légende", "حسب المفتاح")
    add("按字段", "By field", "Por campo", "Par champ", "حسب الحقل")
    add("每层最多", "Max per layer", "Máximo por capa", "Maximum par couche", "الحد لكل طبقة")
    add(
        "超过这个数量就跳过该图层，避免一次写出过多文件。",
        "Above this number the layer is skipped, so one run does not write too many files.",
        "Por encima de este número se omite la capa, para no escribir demasiados archivos de una vez.",
        "Au-dessus de ce nombre, la couche est ignorée, pour ne pas écrire trop de fichiers d’un coup.",
        "إذا تجاوز العدد هذا الحد تُتخطى الطبقة، حتى لا تُكتب ملفات كثيرة دفعة واحدة.",
    )
    add("没有可共用的字段", "No field shared by the layers", "No hay un campo común a las capas", "Aucun champ commun aux couches", "لا يوجد حقل مشترك بين الطبقات")
    add("这个字段没有值", "This field has no values", "Este campo no tiene valores", "Ce champ n’a pas de valeurs", "هذا الحقل بلا قيم")
    add(
        "请先选择导出文件夹。工程还没保存时，需要指定一个文件夹。",
        "Choose an export folder first. An unsaved project needs a folder you pick.",
        "Elige primero la carpeta de exportación. Si el proyecto no está guardado, hay que indicar una carpeta.",
        "Choisissez d’abord un dossier d’export. Un projet non enregistré exige un dossier indiqué par vous.",
        "اختر مجلد التصدير أولًا. إذا لم يُحفظ المشروع، يلزم تحديد مجلد.",
    )
    add("没有图例分类", "No legend classes", "Sin clases de leyenda", "Pas de classes de légende", "لا فئات في المفتاح")
    add("没有字段「%s」", "No field “%s”", "No existe el campo «%s»", "Pas de champ « %s »", "لا يوجد الحقل «%s»")
    add(
        "不同值超过上限 %d。请提高「每层最多」或换一个字段。",
        "Distinct values exceed the limit of %d. Raise “Max per layer” or pick another field.",
        "Los valores distintos superan el tope de %d. Sube «Máximo por capa» o elige otro campo.",
        "Les valeurs distinctes dépassent le plafond de %d. Augmentez « Maximum par couche » ou choisissez un autre champ.",
        "القيم المختلفة تتجاوز الحد %d. ارفع «الحد لكل طبقة» أو اختر حقلًا آخر.",
    )
    add("没有可以导出的分类。%s", "Nothing to export. %s", "No hay clases que exportar. %s", "Aucune classe à exporter. %s", "لا فئات للتصدير. %s")
    add(
        "已导出 %d 个文件到：\n%s",
        "Exported %d files to:\n%s",
        "Se exportaron %d archivos a:\n%s",
        "Exporté %d fichiers vers :\n%s",
        "تم تصدير %d ملفًا إلى:\n%s",
    )
    add(
        "分类有 %d 个，超过上限 %d",
        "%d classes, over the limit of %d",
        "Hay %d clases, por encima del tope de %d",
        "%d classes, au-dessus du plafond de %d",
        "الفئات %d، وتتجاوز الحد %d",
    )
    add(
        "写成 %d 个文件，%d 个没能导出：%s",
        "Wrote %d files; %d could not be exported: %s",
        "Se escribieron %d archivos; %d no se pudieron exportar: %s",
        "%d fichiers écrits ; %d n’ont pas pu être exportés : %s",
        "كُتب %d ملفًا، وتعذر تصدير %d: %s",
    )
    add(
        "管理图层右键菜单。勾选为显示，拖动或用上下箭头改顺序。自定义名称留空就用原来的名字；写了名字后，列表显示成原名(自定义名)，图层右键里只显示括号里的名字。工具条上改过的按钮名字会同步到这里。恢复默认只还原这一页，不动工具条。下面的下拉框用来加入本插件功能。打开这一页时会读取当前右键菜单；若列表还空，先在图层面板上对图层右键一次。",
        "Manage the layer right-click menu. A check means visible. Drag, or use the arrows, to change the order. Leave the custom name blank to keep the original. After you type a name, the list shows Original(custom), and the layer right-click shows only the name in parentheses. A name changed on the toolbar is kept in step here. Reset restores only this page, not the toolbar. The list below adds this plugin’s tools. Opening this page reads the current menu. If the list is still empty, right-click a layer in the Layers panel once.",
        "Gestiona el menú contextual de las capas. La casilla significa visible. Arrastra, o usa las flechas, para cambiar el orden. Deja el nombre en blanco para conservar el original. Si escribes un nombre, la lista muestra Original(personalizado) y el clic derecho de la capa muestra solo el nombre entre paréntesis. Un nombre cambiado en la barra se refleja aquí. Restaurar solo devuelve esta página, no la barra. La lista de abajo añade herramientas de este complemento. Al abrir esta página se lee el menú actual. Si la lista sigue vacía, haz clic derecho una vez sobre una capa en el panel Capas.",
        "Gère le menu contextuel des couches. Une coche signifie visible. Glissez, ou utilisez les flèches, pour changer l’ordre. Laissez le nom vide pour garder l’original. Après un nom saisi, la liste affiche Original(personnalisé) et le clic droit de la couche n’affiche que le nom entre parenthèses. Un nom modifié dans la barre est repris ici. Réinitialiser ne restaure que cette page, pas la barre. La liste ci-dessous ajoute les outils de cette extension. Ouvrir cette page lit le menu actuel. Si la liste est encore vide, faites un clic droit une fois sur une couche dans le panneau Couches.",
        "يدير قائمة النقر بالزر الأيمن على الطبقة. التحديد يعني ظاهرًا. اسحب، أو استخدم الأسهم، لتغيير الترتيب. اترك الاسم فارغًا للإبقاء على الاسم الأصلي. بعد كتابة اسم تظهر القائمة بالشكل الاسم الأصلي(الاسم المخصص)، ونقر الطبقة بالزر الأيمن يعرض الاسم داخل القوسين فقط. الاسم الذي يُغيَّر في شريط الأدوات يتبع هنا. الاستعادة تعيد هذه الصفحة فقط، لا الشريط. القائمة أدناه تضيف أدوات هذه الإضافة. فتح هذه الصفحة يقرأ القائمة الحالية. إذا بقيت القائمة فارغة، انقر بالزر الأيمن مرة على طبقة في لوحة الطبقات.",
    )
    add("并成同一个表", "One table", "Una sola tabla", "Une seule table", "جدول واحد")
    add(
        "不勾选时，每个图层一个工作表，表名是图层名。CSV 本身不能有多个工作表，所以会写成同名的 Excel 文件。勾选后并进同一个 CSV 表：同名字段只出现一次，每个图层的字段都会保留，并加一列记下原来的图层名。",
        "When this is off, each layer is one sheet, named after the layer. CSV itself cannot hold several sheets, so a same-named Excel file is written. When it is on, everything goes into one CSV table: a shared field name appears once, every layer’s fields are kept, and a column records the source layer name.",
        "Sin marcar, cada capa es una hoja con el nombre de la capa. CSV no puede tener varias hojas, así que se escribe un Excel con el mismo nombre. Marcado, todo va a una tabla CSV: un campo con el mismo nombre aparece una vez, se conservan los campos de cada capa y una columna guarda el nombre de la capa de origen.",
        "Décochée, chaque couche est une feuille portant le nom de la couche. Un CSV ne peut pas avoir plusieurs feuilles, donc un fichier Excel du même nom est écrit. Cochée, tout va dans une table CSV : un nom de champ commun n’apparaît qu’une fois, les champs de chaque couche sont gardés, et une colonne retient le nom de la couche d’origine.",
        "بدون تحديد، كل طبقة ورقة باسم الطبقة. CSV لا يحتمل عدة أوراق، فيُكتب ملف Excel بالاسم نفسه. عند التحديد يذهب كل شيء إلى جدول CSV واحد: اسم الحقل المشترك يظهر مرة واحدة، وتُحفظ حقول كل طبقة، ويُضاف عمود باسم الطبقة الأصلية.",
    )
    add(
        "已写入 %s，共 %d 个图层。",
        "Wrote %s, %d layers.",
        "Se escribió %s, %d capas.",
        "Écrit %s, %d couches.",
        "كُتب %s، بعدد %d طبقة.",
    )
    add(
        "已写入 %s。CSV 不能分成多个工作表，已改写成 Excel：每个图层一个表，表名是图层名。",
        "Wrote %s. CSV cannot be split into sheets, so this was written as Excel: one sheet per layer, named after the layer.",
        "Se escribió %s. CSV no se puede partir en hojas, así que se escribió como Excel: una hoja por capa, con el nombre de la capa.",
        "Écrit %s. Un CSV ne peut pas être découpé en feuilles, donc ceci a été écrit en Excel : une feuille par couche, nommée comme la couche.",
        "كُتب %s. CSV لا يُقسَّم إلى أوراق، فكُتب كملف Excel: ورقة لكل طبقة باسم الطبقة.",
    )
    add(
        "只恢复图层右键菜单，不动工具条。",
        "Restore only the layer right-click menu, not the toolbar.",
        "Restaura solo el menú contextual de las capas, no la barra.",
        "Ne restaure que le menu contextuel des couches, pas la barre.",
        "يعيد قائمة النقر بالزر الأيمن على الطبقة فقط، لا شريط الأدوات.",
    )
    add("自定义名称", "Custom name", "Nombre personalizado", "Nom personnalisé", "اسم مخصص")
    add("留空使用原名", "Leave blank to keep the original name", "Déjalo vacío para usar el nombre original", "Laisser vide pour garder le nom d’origine", "اتركه فارغًا للاسم الأصلي")
    add("添加功能", "Add a tool", "Añadir una herramienta", "Ajouter un outil", "إضافة أداة")
    add("添加", "Add", "Añadir", "Ajouter", "إضافة")
    add("移除", "Remove", "Quitar", "Retirer", "إزالة")
    add("合并为一个文件", "Merge into one file", "Unir en un archivo", "Fusionner en un fichier", "دمج في ملف واحد")
    add("合并图层", "Merged layers", "Capas unidas", "Couches fusionnées", "طبقات مدمجة")
    add(
        "这一版 QGIS 不能把多个图层写进同一个文件。",
        "This QGIS version cannot write several layers into one file.",
        "Esta versión de QGIS no puede escribir varias capas en un solo archivo.",
        "Cette version de QGIS ne peut pas écrire plusieurs couches dans un seul fichier.",
        "هذا الإصدار من QGIS لا يستطيع كتابة عدة طبقات في ملف واحد.",
    )
    add(
        "勾选后，多个图层写入同一个文件。",
        "When checked, several layers are written into the same file.",
        "Si está marcado, varias capas se escriben en el mismo archivo.",
        "Si coché, plusieurs couches sont écrites dans le même fichier.",
        "عند التحديد تُكتب عدة طبقات في الملف نفسه.",
    )
    add(
        "这个格式一个文件只能放一个图层。",
        "This format can hold only one layer per file.",
        "Este formato solo admite una capa por archivo.",
        "Ce format ne peut contenir qu’une couche par fichier.",
        "هذا التنسيق يضع طبقة واحدة فقط في كل ملف.",
    )
    add(
        "已写入 %s。DXF 会丢掉大部分属性，只保留几何和图层名。",
        "Wrote %s. DXF drops most attributes and keeps only the geometry and the layer name.",
        "Se escribió %s. DXF pierde la mayoría de los atributos y solo conserva la geometría y el nombre de capa.",
        "Écrit dans %s. Le DXF perd la plupart des attributs et ne garde que la géométrie et le nom de couche.",
        "كُتب %s. يسقط DXF معظم السمات ويبقي الهندسة واسم الطبقة فقط.",
    )
    add(
        "合并文件 %s 里写入了 %d 个图层，%d 个没能写入：%s",
        "Merged file %s received %d layers; %d could not be written: %s",
        "El archivo unido %s recibió %d capas; %d no se pudieron escribir: %s",
        "Le fichier fusionné %s a reçu %d couches ; %d n’ont pas pu être écrites : %s",
        "الملف المدمج %s استقبل %d طبقة، وتعذرت كتابة %d: %s",
    )
    add("清空数据", "Clear data", "Vaciar datos", "Vider les données", "مسح البيانات")
    add("打开编辑", "Start editing", "Abrir edición", "Ouvrir l’édition", "فتح التحرير")
    add("保存关闭", "Save and close", "Guardar y cerrar", "Enregistrer et fermer", "حفظ وإغلاق")
    add("复制到空", "Copy empty", "Copiar vacío", "Copier à vide", "نسخ فارغ")
    add("复制图层", "Copy layer", "Copiar capa", "Copier la couche", "نسخ الطبقة")
    add("图层操作", "Layer actions", "Acciones de capa", "Actions de couche", "عمليات الطبقة")
    add(
        "清空数据、开关编辑，或把当前图层复制成新文件",
        "Clear data, toggle editing, or copy the current layer to a new file",
        "Vacía datos, abre o cierra la edición, o copia la capa actual a un archivo nuevo",
        "Vider les données, ouvrir ou fermer l’édition, ou copier la couche actuelle vers un nouveau fichier",
        "مسح البيانات، أو فتح التحرير وإغلاقه، أو نسخ الطبقة الحالية إلى ملف جديد",
    )
    add(
        "当前没有可处理的矢量图层。",
        "There is no vector layer to work on.",
        "No hay ninguna capa vectorial que tratar.",
        "Aucune couche vectorielle à traiter.",
        "لا توجد طبقة متجهة للمعالجة.",
    )
    add("所有图层数据已清空", "All layer data has been cleared", "Se vaciaron los datos de todas las capas", "Les données de toutes les couches ont été vidées", "مُسحت بيانات كل الطبقات")
    add("所有图层编辑模式已打开", "Editing is on for every layer", "La edición está abierta en todas las capas", "L’édition est ouverte pour toutes les couches", "فُتح التحرير لكل الطبقات")
    add(
        "所有图层已保存并退出编辑模式",
        "Every layer was saved and left editing",
        "Todas las capas se guardaron y salieron de la edición",
        "Toutes les couches ont été enregistrées et ont quitté l’édition",
        "حُفظت كل الطبقات وخرجت من التحرير",
    )
    add("确认清空", "Confirm clear", "Confirmar vaciado", "Confirmer le vidage", "تأكيد المسح")
    add(
        "将删除当前工程里全部矢量图层的全部要素。图层还在，要素删掉后不能恢复。\n请输入 OK 确认：",
        "This deletes every feature in every vector layer of the current project. The layers stay, and deleted features cannot be recovered.\nType OK to confirm:",
        "Se borrarán todas las entidades de todas las capas vectoriales del proyecto actual. Las capas siguen, y lo borrado no se puede recuperar.\nEscribe OK para confirmar:",
        "Cela supprime toutes les entités de toutes les couches vectorielles du projet en cours. Les couches restent, et les entités supprimées ne peuvent pas être récupérées.\nSaisissez OK pour confirmer :",
        "سيُحذف كل معلم في كل طبقة متجهة في المشروع الحالي. الطبقات تبقى، والمعالم المحذوفة لا تُسترجع.\nاكتب OK للتأكيد:",
    )
    add("二次确认", "Confirm again", "Segunda confirmación", "Deuxième confirmation", "تأكيد ثانٍ")
    add(
        "确认删除全部要素？这一步不能返回，也不能撤销。",
        "Delete every feature? This step cannot be undone.",
        "¿Borrar todas las entidades? Este paso no se puede deshacer.",
        "Supprimer toutes les entités ? Cette étape est irréversible.",
        "حذف كل المعالم؟ هذه الخطوة لا تُرجع ولا تُلغى.",
    )
    add(
        "连同全部要素一起复制，样式与所选图层相同。",
        "Copy every feature as well. The style matches the selected layer.",
        "Copia también todas las entidades. El estilo es el de la capa elegida.",
        "Copie aussi toutes les entités. Le style est celui de la couche choisie.",
        "انسخ كل المعالم أيضًا. النمط يطابق الطبقة المختارة.",
    )
    add(
        "不复制要素，只保留字段和样式。",
        "Do not copy features. Keep only the fields and the style.",
        "No copia entidades. Solo conserva los campos y el estilo.",
        "Ne copie pas les entités. Ne conserve que les champs et le style.",
        "لا تنسخ المعالم. أبقِ الحقول والنمط فقط.",
    )
    add(
        "这个图层没有文件路径，默认保存到工程所在文件夹。",
        "This layer has no file path. The default folder is the project folder.",
        "Esta capa no tiene ruta de archivo. La carpeta predeterminada es la del proyecto.",
        "Cette couche n’a pas de chemin de fichier. Le dossier par défaut est celui du projet.",
        "هذه الطبقة بلا مسار ملف. المجلد الافتراضي هو مجلد المشروع.",
    )
    add("_空", "_empty", "_vacio", "_vide", "_empty")
    add("保存复制图层", "Save copied layer", "Guardar la capa copiada", "Enregistrer la couche copiée", "حفظ الطبقة المنسوخة")
    add("删除全部", "Delete all", "Borrar todo", "Tout supprimer", "حذف الكل")
    add(
        "请先在图层面板选中一个矢量图层。",
        "Select a vector layer in the Layers panel first.",
        "Selecciona primero una capa vectorial en el panel Capas.",
        "Sélectionnez d’abord une couche vectorielle dans le panneau Couches.",
        "حدد أولًا طبقة متجهة في لوحة الطبقات.",
    )
    add("复制当前图层", "Copy the current layer", "Copiar la capa actual", "Copier la couche actuelle", "نسخ الطبقة الحالية")
    add("复制当前图层为空", "Copy the current layer empty", "Copiar la capa actual vacía", "Copier la couche actuelle à vide", "نسخ الطبقة الحالية فارغة")
    add(
        "当前所选图层：%s\n路径：%s\n原格式：%s\n%s\n\n下一步选择保存位置。默认就在这个文件夹，格式默认与原图层相同。",
        "Selected layer: %s\nPath: %s\nOriginal format: %s\n%s\n\nNext, choose where to save. The default is this folder, and the format defaults to the original layer.",
        "Capa seleccionada: %s\nRuta: %s\nFormato original: %s\n%s\n\nA continuación elige dónde guardar. Por defecto es esta carpeta, y el formato es el de la capa original.",
        "Couche sélectionnée : %s\nChemin : %s\nFormat d’origine : %s\n%s\n\nEnsuite, choisissez où enregistrer. Par défaut c’est ce dossier, et le format est celui de la couche d’origine.",
        "الطبقة المحددة: %s\nالمسار: %s\nالتنسيق الأصلي: %s\n%s\n\nبعدها اختر مكان الحفظ. الافتراضي هذا المجلد، والتنسيق يطابق الطبقة الأصلية.",
    )
    add("继续", "Continue", "Continuar", "Continuer", "متابعة")
    add(
        "已复制图层「%s」到：\n%s",
        "Copied layer “%s” to:\n%s",
        "Capa «%s» copiada a:\n%s",
        "Couche « %s » copiée vers :\n%s",
        "نُسخت الطبقة «%s» إلى:\n%s",
    )
    add(
        "以下图层清空失败：\n%s",
        "These layers could not be cleared:\n%s",
        "No se pudieron vaciar estas capas:\n%s",
        "Ces couches n’ont pas pu être vidées :\n%s",
        "تعذر مسح هذه الطبقات:\n%s",
    )
    add(
        "以下图层未能打开编辑：\n%s",
        "Editing could not be started on these layers:\n%s",
        "No se pudo abrir la edición en estas capas:\n%s",
        "L’édition n’a pas pu être ouverte sur ces couches :\n%s",
        "تعذر فتح التحرير لهذه الطبقات:\n%s",
    )
    add(
        "以下图层保存失败：\n%s",
        "These layers could not be saved:\n%s",
        "No se pudieron guardar estas capas:\n%s",
        "Ces couches n’ont pas pu être enregistrées :\n%s",
        "تعذر حفظ هذه الطبقات:\n%s",
    )
    add("没有写成文件。", "The file was not written.", "No se escribió el archivo.", "Le fichier n’a pas été écrit.", "لم يُكتب الملف.")
    add("文件已保存：%s", "File saved: %s", "Archivo guardado: %s", "Fichier enregistré : %s", "حُفظ الملف: %s")
    add("线标注", "Line marks", "Marcas de línea", "Repères de ligne", "علامات الخط")
    add(
        "在所选线的两端标出起点和终点，并显示长度。不改图层数据。",
        "Mark the start and end of the selected lines and show the length. Layer data is not changed.",
        "Marca el inicio y el final de las líneas seleccionadas y muestra la longitud. No cambia los datos de la capa.",
        "Marque le début et la fin des lignes sélectionnées et affichez la longueur. Les données de la couche ne changent pas.",
        "ضع علامة على بداية ونهاية الخطوط المحددة واعرض الطول. بيانات الطبقة لا تتغير.",
    )
    add("%.2f米", "%.2f m", "%.2f m", "%.2f m", "%.2f م")
    add(
        "列出所选线及长度。勾选会改 QGIS 选中；名单只在地图/表里重新选线后更新。",
        "List the selected lines and their lengths. Checking a row changes the QGIS selection. The list updates only after you select lines again on the map or in the table.",
        "Lista las líneas seleccionadas y su longitud. Marcar una fila cambia la selección de QGIS. La lista solo se actualiza cuando vuelves a seleccionar líneas en el mapa o en la tabla.",
        "Liste les lignes sélectionnées et leur longueur. Cocher une ligne change la sélection QGIS. La liste ne se met à jour qu’après une nouvelle sélection sur la carte ou dans la table.",
        "يسرد الخطوط المحددة وأطوالها. تحديد صف يغيّر تحديد QGIS. القائمة لا تتحدث إلا بعد إعادة تحديد الخطوط على الخريطة أو في الجدول.",
    )
    add("全部", "All", "Todas", "Tout", "الكل")
    add("起点%s", "Start %s", "Inicio %s", "Début %s", "البداية %s")
    add("终点%s", "End %s", "Fin %s", "Fin %s", "النهاية %s")
    add("起点%d  %s", "Start %d  %s", "Inicio %d  %s", "Début %d  %s", "البداية %d  %s")
    add(
        "只标前 %d 条，其余未显示",
        "Only the first %d are marked; the rest are not shown",
        "Solo se marcan las %d primeras; el resto no se muestra",
        "Seules les %d premières sont marquées ; le reste n’est pas affiché",
        "تُعلَّم أول %d فقط، والباقي غير معروض",
    )
    add("工具条", "Toolbar", "Barra", "Barre", "شريط الأدوات")
    add("系统属性", "Right-click", "Clic derecho", "Clic droit", "النقرة اليمنى")
    add("文件", "File", "Archivo", "Fichier", "ملف")
    add("保存合并文件", "Save merged file", "Guardar el archivo unido", "Enregistrer le fichier fusionné", "حفظ الملف المدمج")
    add("请先选择要保存的文件。", "Choose the file to save first.", "Elige primero el archivo que quieres guardar.", "Choisissez d’abord le fichier à enregistrer.", "اختر أولًا الملف الذي تريد حفظه.")
    add("这个文件已经存在，是否覆盖？", "This file already exists. Overwrite it?", "Este archivo ya existe. ¿Sobrescribirlo?", "Ce fichier existe déjà. Le remplacer ?", "هذا الملف موجود مسبقًا. هل تريد استبداله؟")
    add(
        "勾选后，多个图层写入你选定的那一个文件。",
        "When checked, the layers are written into the one file you choose.",
        "Si está marcado, las capas se escriben en el archivo que elijas.",
        "Si coché, les couches sont écrites dans le fichier que vous choisissez.",
        "عند التحديد تُكتب الطبقات في الملف الذي تختاره.",
    )
    add(
        "勾选后，这些图层的要素写入同一个文件，并加一列记下原来的图层名。点、线、面可以放在一起。",
        "When checked, features from these layers go into the same file, with a column naming the source layer. Points, lines, and polygons can share that file.",
        "Si está marcado, las entidades de estas capas van al mismo archivo, con una columna que indica la capa de origen. Puntos, líneas y polígonos pueden ir juntos.",
        "Si coché, les entités de ces couches vont dans le même fichier, avec une colonne qui nomme la couche d’origine. Points, lignes et polygones peuvent y cohabiter.",
        "عند التحديد تذهب معالم هذه الطبقات إلى الملف نفسه، مع عمود يذكر اسم الطبقة الأصلية. يمكن أن تجتمع النقاط والخطوط والمضلعات في هذا الملف.",
    )
    add("请先选择一个图层。", "Choose a layer first.", "Elige primero una capa.", "Choisissez d’abord une couche.", "اختر طبقة أولًا.")
    add("请先选择字段。", "Choose a field first.", "Elige primero un campo.", "Choisissez d’abord un champ.", "اختر حقلًا أولًا.")
    add("这个图层没有可用字段。", "This layer has no field to use.", "Esta capa no tiene ningún campo que usar.", "Cette couche n’a aucun champ utilisable.", "هذه الطبقة بلا حقل يمكن استخدامه.")
    return rows


_ROWS = _rows()
EN = {item[0]: item[1] for item in _ROWS}
ES = {item[0]: item[2] for item in _ROWS}
FR = {item[0]: item[3] for item in _ROWS}
AR = {item[0]: item[4] for item in _ROWS}
