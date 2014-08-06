# -*- coding: utf-8 -*-

"""Parse OOXML structure.

.. moduleauthor:: Aleksandar Erkalovic <aerkalov@gmail.com>

"""

import zipfile
import logging

from lxml import etree

from . import doc, NAMESPACES


logger = logging.getLogger('ooxml')


def _name(name):
    return name.format(**NAMESPACES)


def parse_previous_properties(doc, paragraph, prop):
    if not paragraph:
        return

    style = prop.find(_name('{{{w}}}rStyle'))

    if style is not None:
        paragraph.rpr['style'] = style.attrib[_name('{{{w}}}val')]

    color = prop.find(_name('{{{w}}}color'))

    if color is not None:
        paragraph.rpr['color'] = color.attrib[_name('{{{w}}}val')]

    rtl = prop.find(_name('{{{w}}}rtl'))

    if rtl is not None:
        paragraph.rpr['rtl'] = rtl.attrib[_name('{{{w}}}val')]

    sz = prop.find(_name('{{{w}}}sz'))

    if sz is not None:
        paragraph.rpr['sz'] = sz.attrib[_name('{{{w}}}val')]

    b = prop.find(_name('{{{w}}}b'))

    if b is not None:        
        # todo
        # check b = on and not off
        paragraph.rpr['b'] = True


def parse_paragraph_properties(doc, paragraph, prop):
    if not paragraph:
        return

    style = prop.find(_name('{{{w}}}pStyle'))

    if style is not None:
        paragraph.style_id = style.attrib[_name('{{{w}}}val')]

    numpr = prop.find(_name('{{{w}}}numPr'))

    if numpr is not None:
        ilvl = numpr.find(_name('{{{w}}}ilvl'))

        if ilvl is not None:
            paragraph.ilvl = int(ilvl.attrib[_name('{{{w}}}val')])

        numid = numpr.find(_name('{{{w}}}numId'))

        if numid is not None:
            paragraph.numid = int(numid.attrib[_name('{{{w}}}val')])

    rpr = prop.find(_name('{{{w}}}rPr'))

    if rpr is not None:
        parse_previous_properties(doc, paragraph, rpr)

    jc = prop.find(_name('{{{w}}}jc'))

    if jc is not None:
        paragraph.ppr['jc'] = jc.attrib[_name('{{{w}}}val')]

    ind = prop.find(_name('{{{w}}}ind'))

    if ind is not None:
        paragraph.ppr['ind'] = {}
        
        if _name('{{{w}}}left') in ind.attrib:
            paragraph.ppr['ind']['left'] = ind.attrib[_name('{{{w}}}left')]


    # w:ind - left leftChars right hanging firstLine

def parse_drawing(document, container, elem):
    blip = elem.xpath('.//a:blip', namespaces=NAMESPACES)[0]        
    _rid =  blip.attrib[_name('{{{r}}}embed')]

    img = doc.Image(_rid)
    container.elements.append(img)


def parse_footnote(document, container, elem):
    _rid =  elem.attrib[_name('{{{w}}}id')]

    foot = doc.Footnote(_rid)
    container.elements.append(foot)


def parse_alternate(document, container, elem):
    txtbx = elem.find('.//'+_name('{{{w}}}txbxContent'))
    paragraphs = []

    if not txtbx:
        return

    for el in txtbx:
        if el.tag == _name('{{{w}}}p'):
            paragraphs.append(parse_paragraph(document, el))

    textbox = doc.TextBox(paragraphs)
    container.elements.append(textbox)
    

def parse_text(document, container, element):
    txt = None

    alternate = element.find(_name('{{{mc}}}AlternateContent'))

    if alternate is not None:
        parse_alternate(document, container, alternate)

    br = element.find(_name('{{{w}}}br'))

    if br is not None:
        if _name('{{{w}}}type') in br.attrib:
            _type = br.attrib[_name('{{{w}}}type')]        

            brk = doc.Break(_type)
            container.elements.append(brk)

    t = element.find(_name('{{{w}}}t'))

    if t is not None:
        txt = doc.Text(t.text)

        container.elements.append(txt)

    rpr = element.find(_name('{{{w}}}rPr'))

    if rpr is not None:
        parse_previous_properties(document, txt, rpr)

    r = element.find(_name('{{{w}}}r'))

    if r is not None:
        parse_text(document, container, r)

    foot = element.find(_name('{{{w}}}footnoteReference'))

    if foot is not None:
        parse_footnote(document, container, foot)

    sym = element.find(_name('{{{w}}}sym'))

    if sym is not None:
        _font = sym.attrib[_name('{{{w}}}font')]
        _char = sym.attrib[_name('{{{w}}}char')]

        container.elements.append(doc.Symbol(font=_font, character=_char))

    image = element.find(_name('{{{w}}}drawing'))

    if image is not None:
        parse_drawing(document, container, image)

    return


def parse_paragraph(document, par):
    paragraph = doc.Paragraph()    
    paragraph.document = document

    for elem in par:
        if elem.tag == _name('{{{w}}}pPr'):
            parse_paragraph_properties(document, paragraph, elem)

        if elem.tag == _name('{{{w}}}r'):
            parse_text(document, paragraph, elem)      

        if elem.tag == _name('{{{m}}}oMath'):
            _m = doc.Math()
            paragraph.elements.append(_m)

        if elem.tag == _name('{{{w}}}hyperlink'):
            try:
                t = doc.Link(elem.attrib[_name('{{{r}}}id')])

                parse_text(document, t, elem)            

                paragraph.elements.append(t)            
            except:
                logger.error('Error with with hyperlink [%s].', str(elem.attrib.items()))

    return paragraph


def parse_table(document, tbl):
    table = doc.Table()

    for tr in tbl.xpath('./w:tr', namespaces=NAMESPACES):
        columns = []

        for tc in tr.xpath('./w:tc', namespaces=NAMESPACES):
            _p = []

            for p in tc.xpath('./w:p', namespaces=NAMESPACES):
                _p.append(parse_paragraph(document, p))

            columns.append(_p)

        table.rows.append(columns)

    return table


def parse_document(xmlcontent):
    document = etree.fromstring(xmlcontent)

    body = document.xpath('.//w:body', namespaces=NAMESPACES)[0]

    document = doc.Document()

    for elem in body:
        if elem.tag == _name('{{{w}}}p'):
            document.elements.append(parse_paragraph(document, elem))

        if elem.tag == _name('{{{w}}}tbl'):
            document.elements.append(parse_table(document, elem))

    return document


def parse_relationship(document, xmlcontent):
    doc = etree.fromstring(xmlcontent)

    for elem in doc:
        if elem.tag == _name('{{{pr}}}Relationship'):
            rel = {'target': elem.attrib['Target'],
                   'type': elem.attrib['Type'],
                   'target_mode': elem.attrib.get('TargetMode', 'Internal')}

            document.relationships[elem.attrib['Id']] = rel


def parse_style(document, xmlcontent):
    styles = etree.fromstring(xmlcontent)
    document.styles = {}

    for style in styles.xpath('.//w:style', namespaces=NAMESPACES):
        st = doc.Style()

        st.style_id = style.attrib[_name('{{{w}}}styleId')]

        name = style.find(_name('{{{w}}}name'))
        if name is not None:
            st.name = name.attrib[_name('{{{w}}}val')]

        based_on = style.find(_name('{{{w}}}basedOn'))

        if based_on is not None:
            st.based_on = based_on.attrib[_name('{{{w}}}val')]

        document.styles[st.style_id] = st

        rpr = style.find(_name('{{{w}}}rPr'))

        if rpr is not None:
            parse_previous_properties(document, st, rpr)


        ppr = style.find(_name('{{{w}}}pPr'))

        if ppr is not None:
           parse_paragraph_properties(document, st, ppr)


def parse_footnotes(document, xmlcontent):
    styles = etree.fromstring(xmlcontent)
    document.footnotes = {}

    for style in styles.xpath('.//w:footnote', namespaces=NAMESPACES):
        _type = style.attrib.get(_name('{{{w}}}type'), None)

        # don't know what to do with these now
        if _type in ['separator', 'continuationSeparator', 'continuationNotice']:
            continue

        p = parse_paragraph(document, style.find(_name('{{{w}}}p')))

        document.footnotes[style.attrib[_name('{{{w}}}id')]] = p


def parse_numbering(document, xmlcontent):
    numbering = etree.fromstring(xmlcontent)
    document.numbering = {}

    for abstruct_num in numbering.xpath('.//w:abstractNum', namespaces=NAMESPACES):
        numb = {}

        for lvl in abstruct_num.xpath('./w:lvl', namespaces=NAMESPACES):
            ilvl = int(lvl.attrib[_name('{{{w}}}ilvl')])

            fmt = lvl.find(_name('{{{w}}}numFmt'))
            numb[ilvl] = {'numFmt': fmt.attrib[_name('{{{w}}}val')]}

        document.numbering[abstruct_num.attrib[_name('{{{w}}}abstractNumId')]] = numb


def parse_from_file(file_object):
    logger.info('Parsing %s file.', file_object.file_name)

    # Read the files
    doc_content = file_object.read_file('document.xml')
    
    # Parse the document
    document = parse_document(doc_content)

    try:    
        style_content = file_object.read_file('styles.xml')
        parse_style(document, style_content)        
    except KeyError:
        logger.warning('Could not read styles.')

    try:        
        doc_rel_content = file_object.read_file('_rels/document.xml.rels')
        parse_relationship(document, doc_rel_content)
    except KeyError:
        logger.warning('Could not read relationships.')

    try:    
        footnotes_content = file_object.read_file('footnotes.xml')
        parse_footnotes(document, footnotes_content)    
    except KeyError:
        logger.warning('Could not read footnotes.')

    try:
        numbering_content = file_object.read_file('numbering.xml')
        parse_numbering(document, numbering_content)    
    except KeyError:
        logger.warning('Could not read numbering.')

    return document
