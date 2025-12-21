const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

async function generatePDF(htmlFile, outputPdf) {
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  try {
    const page = await browser.newPage();
    
    // Read the HTML file
    const htmlPath = path.resolve(__dirname, '..', 'public', htmlFile);
    const htmlContent = fs.readFileSync(htmlPath, 'utf8');
    
    // Load the HTML content
    await page.setContent(htmlContent, {
      waitUntil: 'networkidle0'
    });
    
    // Generate PDF with optimal settings
    const outputPath = path.resolve(__dirname, '..', 'public', outputPdf);
    await page.pdf({
      path: outputPath,
      format: 'Letter',
      printBackground: true,
      margin: {
        top: '0.5in',
        right: '0.5in',
        bottom: '0.5in',
        left: '0.5in'
      }
    });
    
    console.log(`✅ Generated: ${outputPdf}`);
  } catch (error) {
    console.error(`❌ Error generating ${outputPdf}:`, error);
    throw error;
  } finally {
    await browser.close();
  }
}

async function generateAllForms() {
  console.log('🚀 Starting PDF generation...\n');
  
  const forms = [
    {
      html: 'Missouri-Residential-Rental-Application.html',
      pdf: 'Missouri-Residential-Rental-Application.pdf'
    }
    // Add more forms here as needed
  ];
  
  for (const form of forms) {
    await generatePDF(form.html, form.pdf);
  }
  
  console.log('\n✨ All PDFs generated successfully!');
}

// Run the script
generateAllForms().catch(error => {
  console.error('❌ Fatal error:', error);
  process.exit(1);
});

